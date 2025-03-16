import streamlit as st
import pandas as pd
from streamlit.components.v1 import html
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import TypedDict, List, Annotated
import operator
import time
from database import init_db, get_user_by_username, verify_password, update_last_login

# Set page config
st.set_page_config(
    page_title="AI Career Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Remove Streamlit UI elements
st.markdown("""
<style>
    header { visibility: hidden; }
    .stApp > header { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    [data-testid="manage-app-button"] { display: none; }
    [data-testid="stHeader"] [data-testid="stDecoration"] { display: none; }
    [data-testid="stActionButton"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# Professional CSS styling
st.markdown("""
<style>
    .main { background-color: #ffffff; }
    .stButton>button {
        background-color: #2c3e50;
        color: white;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    .stTextInput input, .stTextArea textarea {
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 10px;
    }
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    .stMarkdown h1 {
        color: #2c3e50;
        border-bottom: 2px solid #2c3e50;
    }
    .stSidebar {
        background-color: #f8f9fa;
        border-right: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
init_db()

# Get secrets
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
PINECONE_API_KEY = st.secrets["PINECONE_API_KEY"]
INDEX_NAME = "rajan"

# Define State for LangGraph
class AgentState(TypedDict):
    resume_text: str
    jobs: List[dict]
    history: Annotated[List[str], operator.add]
    current_response: str
    selected_job: dict

# Initialize Pinecone
def init_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    if INDEX_NAME not in pc.list_indexes().names():
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-west-2")
        )
        while not pc.describe_index(INDEX_NAME).status['ready']:
            time.sleep(1)
    return pc.Index(INDEX_NAME)

index = init_pinecone()

# Initialize models
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
llm = ChatGroq(model="llama3-8b-8192", temperature=0, api_key=GROQ_API_KEY)

# LangGraph workflow
def retrieve_jobs(state: AgentState):
    query_embedding = embedding_model.encode(state["resume_text"]).tolist()
    results = index.query(
        vector=query_embedding,
        top_k=100,
        include_metadata=True,
        namespace="jobs"
    )
    return {"jobs": [match.metadata for match in results.matches if match.metadata]}

def generate_analysis(state: AgentState):
    job_texts = "\n\n".join([f"Title: {job['Job Title']}\nCompany: {job['Company Name']}" 
                            for job in state["jobs"]])
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You're a career advisor. Analyze these jobs:"),
        ("human", "Resume: {resume_text}\nJobs:\n{job_texts}")
    ])
    messages = prompt_template.format_messages(
        resume_text=state["resume_text"],
        job_texts=job_texts
    )
    response = llm.invoke(messages)
    return {"current_response": response.content}

def tailor_resume(state: AgentState):
    job = state["selected_job"]
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Tailor this resume for the job:"),
        ("human", "Job: {job_title}\n{job_description}\nResume: {resume_text}")
    ])
    messages = prompt_template.format_messages(
        job_title=job['Job Title'],
        job_description=job['Job Description'],
        resume_text=state["resume_text"]
    )
    response = llm.invoke(messages)
    return {"current_response": response.content}

workflow = StateGraph(AgentState)
workflow.add_node("retrieve_jobs", retrieve_jobs)
workflow.add_node("generate_analysis", generate_analysis)
workflow.add_node("tailor_resume", tailor_resume)
workflow.set_entry_point("retrieve_jobs")
workflow.add_edge("retrieve_jobs", "generate_analysis")
workflow.add_conditional_edges("generate_analysis", 
                              lambda x: "tailor_resume" if x.get("selected_job") else END,
                              {"tailor_resume": "tailor_resume", END: END})
workflow.add_edge("tailor_resume", END)
app = workflow.compile()

def display_jobs_table(jobs):
    jobs_df = pd.DataFrame([{
        "Title": job.get("Job Title", ""),
        "Company": job.get("Company Name", ""),
        "Location": job.get("Location", ""),
        "Job Portal Posted Time": job.get("Posted Time", ""),  # Original portal text
        "Salary": job.get("Salary", ""),
        "Experience": job.get("Years of Experience", ""),
        "Pharma AI Posted Date": job.get("Posted date of Pharma AI", ""),  # New column
        "Link": job.get("Job Link", "")
    } for job in jobs])

    st.dataframe(
        jobs_df,
        column_config={
            "Link": st.column_config.LinkColumn("View"),
            "Job Portal Posted Time": st.column_config.TextColumn(
                "Portal Post Time",
                help="Original job portal posting text"
            ),
            "Pharma AI Posted Date": st.column_config.TextColumn(
                "Pharma AI Processed",
                help="Date when Pharma AI processed the job"
            ),
            "Salary": st.column_config.NumberColumn(
                "Salary",
                format="$%d"
            )
        },
        hide_index=True,
        use_container_width=True
    )

# Authentication
def authentication_ui():
    with st.form("Login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            user = get_user_by_username(username)
            if user and verify_password(user[2], password):
                update_last_login(username)
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")

# Main app
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.agent_state = {
        "resume_text": "",
        "jobs": [],
        "current_response": "",
        "selected_job": None,
        "history": []  # Added missing field
    }

if not st.session_state.logged_in:
    authentication_ui()
    st.stop()

# Sidebar
with st.sidebar:
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    st.write(f"User: {st.session_state.get('username', '')}")

# Main interface
def main_application():
    with st.form("resume_analysis"):
        resume_text = st.text_area("Paste your resume", height=250)
        if st.form_submit_button("Analyze"):
            st.session_state.agent_state.update({
                "resume_text": resume_text,
                "selected_job": None,
                "history": []  # Reset history on new analysis
            })
            for event in app.stream(st.session_state.agent_state):
                st.session_state.agent_state.update(event.get("__end__", {}))

    if st.session_state.agent_state["current_response"]:
        st.subheader("Analysis")
        st.write(st.session_state.agent_state["current_response"])

    if st.session_state.agent_state["jobs"]:
        st.subheader("Matching Jobs")
        display_jobs_table(st.session_state.agent_state["jobs"])

        selected_job = st.selectbox(
            "Select job to tailor resume",
            [job["Job Title"] for job in st.session_state.agent_state["jobs"]]
        )
        if selected_job:
            st.session_state.agent_state["selected_job"] = next(
                job for job in st.session_state.agent_state["jobs"]
                if job["Job Title"] == selected_job
            )
            if st.button("Generate Tailoring Suggestions"):
                result = tailor_resume(st.session_state.agent_state)
                st.session_state.agent_state.update(result)
                st.subheader("Tailoring Suggestions")
                st.write(st.session_state.agent_state["current_response"])

main_application()

# Add Tableau visualization at the bottom
st.markdown("<hr>", unsafe_allow_html=True)
st.subheader("H1B Visa Sponsorships (Leading Life Science Companies 2024)")

# Add this at the bottom after your main application code
from streamlit.components.v1 import html

tableau_code = """
<div class='tableauPlaceholder' id='viz1738751341715' style='position: relative; overflow: hidden;'>
<object class='tableauViz' style='display:none;'>
<param name='host_url' value='https%3A%2F%2Fpublic.tableau.com%2F' />
<param name='embed_code_version' value='3' />
<param name='site_root' value='' />
<param name='name' value='nfljnvjlnjvlnjlv/LifeScience' />
<param name='tabs' value='no' />
<param name='toolbar' value='hidden' />
<param name='static_image' value='https://public.tableau.com/static/images/nf/nfljnvjlnjvlnjlv/LifeScience/1.png' />
<param name='animate_transition' value='yes' />
<param name='display_static_image' value='yes' />
<param name='display_spinner' value='yes' />
<param name='display_overlay' value='no' />
<param name='display_count' value='no' />
<param name='language' value='en-US' />
<param name='filter' value='publish=yes' />
</object>
</div>
<script type='text/javascript'>
document.addEventListener('DOMContentLoaded', function() {
    var divElement = document.getElementById('viz1738751341715');
    var vizElement = divElement.getElementsByTagName('object')[0];
    
    // Hide Tableau branding and controls
    vizElement.style.width = '100%';
    vizElement.style.height = '600px';  // Fixed height or use calc(100vh - 400px)
    vizElement.style.border = 'none';
    
    // Remove unwanted elements after load
    function cleanTableauUI() {
        try {
            // Remove Tableau public banner
            var publicBanner = vizElement.contentDocument.querySelector('.tab-public-banner');
            if (publicBanner) publicBanner.style.display = 'none';
            
            // Remove download and share buttons
            var toolbar = vizElement.contentDocument.querySelector('.tab-toolbar');
            if (toolbar) toolbar.style.display = 'none';
            
            // Remove "View in Tableau Public" text
            var viewLinks = vizElement.contentDocument.querySelectorAll('a[target="_blank"]');
            viewLinks.forEach(link => link.style.display = 'none');
        } catch(e) {
            // Retry if iframe not loaded yet
            setTimeout(cleanTableauUI, 100);
        }
    }
    
    // Initial cleanup attempt
    cleanTableauUI();
    
    // Add resize observer
    new ResizeObserver(entries => {
        vizElement.style.height = '600px';  // Maintain fixed height or adjust as needed
    }).observe(divElement);

    // Load Tableau script
    var scriptElement = document.createElement('script');
    scriptElement.src = 'https://public.tableau.com/javascripts/api/viz_v1.js';
    vizElement.parentNode.insertBefore(scriptElement, vizElement);
});
</script>
"""


html(tableau_code, width=1200, height=650, scrolling=False)
