import os
from dotenv import load_dotenv

# Load standard .env configuration
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(BASE_DIR, "sources")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")
FAISS_DB_DIR = os.path.join(BASE_DIR, "faiss_db")
DB_PATH = os.path.join(BASE_DIR, "aria_enterprise.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Ingestion configuration
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".csv"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB limit

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_FAST_MODEL = "llama-3.1-8b-instant"  # fast routing / classification

# Embedding Model configuration
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Reranker configuration
RERANK_MODEL_NAME = "ms-marco-MiniLM-L-6-v2"

# Server configuration
API_HOST = "0.0.0.0"
API_PORT = 8000
WS_URL = f"ws://localhost:{API_PORT}/ws"

# Agent configuration
AGENT_CONFIDENCE_THRESHOLD = 0.55   # Minimum score to select an agent
MULTI_AGENT_THRESHOLD = 0.15        # Score gap to trigger multi-agent collaboration
AGENT_DOMAINS = [
    "security",
    "network",
    "hardware",
    "devops",
    "infrastructure",
    "hr",
    "cloud",
    "general"
]

# Tool configuration
HIGH_RISK_TOOLS = {"restart_service", "escalate_incident", "simulate_password_reset"}
TOOL_TIMEOUT_SECONDS = 30

# Analytics configuration
ANALYTICS_RETENTION_DAYS = 30
