import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import SOURCES_DIR, API_HOST, API_PORT
from backend.database.connection import init_db, seed_tickets_if_empty
from backend.api.routes import router as rest_router
from backend.api.websocket import router as ws_router

app = FastAPI(
    title="ARIA Enterprise AI Operating System Backend",
    description="Production-grade asynchronous FastAPI backend providing hybrid RAG search, Multi-Tier Memory, and drag-and-drop document parsing for ARIA.",
    version="1.0.0"
)

# CORS Middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount APIRouters
app.include_router(rest_router)
app.include_router(ws_router)

@app.on_event("startup")
async def startup_event():
    """Initializes local storage directories and database tables on startup."""
    print("Starting up ARIA Enterprise Backend...")
    os.makedirs(SOURCES_DIR, exist_ok=True)
    # Validate SQLite connection and set tables
    init_db()
    seed_tickets_if_empty()
    print("SQLite database tables and standard values initialized successfully.")

@app.get("/")
def read_root():
    return {"status": "Online", "service": "ARIA Enterprise OS Backend", "version": "1.0.0"}

def run_server():
    """Starts the Uvicorn ASGI server."""
    print(f"Launching Uvicorn backend listening at http://{API_HOST}:{API_PORT}...")
    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, log_level="info", reload=False)

if __name__ == "__main__":
    run_server()
