import streamlit as st
import pandas as pd
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
        top_k=30,
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

# Job display with original LinkedIn text
def display_jobs_table(jobs):
    jobs_df = pd.DataFrame([{
        "Title": job.get("Job Title", ""),
        "Company": job.get("Company Name", ""),
        "Location": job.get("Location", ""),
        "Posted": job.get("Posted Time", ""),  # Raw LinkedIn text
        "Salary": job.get("Salary", ""),
        "Experience": job.get("Years of Experience", ""),
        "Link": job.get("Job Link", "")
    } for job in jobs])

    st.dataframe(
        jobs_df,
        column_config={
            "Link": st.column_config.LinkColumn("View"),
            "Posted": st.column_config.TextColumn(
                "Posted",
                help="Original LinkedIn posting text"
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
