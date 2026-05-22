import os
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from backend.config import ALLOWED_EXTENSIONS
from backend.database.connection import get_db_connection
from backend.services.ingestion import enqueue_document

router = APIRouter()

class TicketCreateSchema(BaseModel):
    title: str
    description: str = ""
    category: str = "General"
    priority: str = "Medium"

@router.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Receives drag-and-drop file uploads and schedules them for async ingestion."""
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Approved extensions: {', '.join(ALLOWED_EXTENSIONS)}"
        )
        
    try:
        file_bytes = await file.read()
        res = enqueue_document(file.filename, file_bytes)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule upload: {str(e)}")

@router.get("/api/ingestion/status")
async def get_ingestion_status():
    """Returns a list of all ingested documents and their background indexing states."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingestion_status ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    docs = []
    for r in rows:
        docs.append({
            "file_name": r["file_name"],
            "status": r["status"],
            "progress": r["progress"],
            "error_message": r["error_message"],
            "timestamp": r["timestamp"]
        })
    return docs

@router.get("/api/tickets")
async def list_tickets():
    """Lists all active and resolved support tickets in SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    tickets = []
    for r in rows:
        tickets.append({
            "ticket_id": r["ticket_id"],
            "title": r["title"],
            "description": r["description"],
            "status": r["status"],
            "category": r["category"],
            "priority": r["priority"],
            "created_at": r["created_at"]
        })
    return tickets

@router.post("/api/tickets")
async def create_ticket(schema: TicketCreateSchema):
    """Creates a new autonomous IT support ticket in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Generate unique ticket ID
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    ticket_id = f"IT-{1487 + count}"
    
    try:
        cursor.execute("""
            INSERT INTO tickets (ticket_id, title, description, status, category, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            schema.title,
            schema.description,
            "Open",
            schema.category,
            schema.priority,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        return {"message": "Support ticket created successfully.", "ticket_id": ticket_id, "status": "Open"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to create ticket: {str(e)}")

@router.get("/api/preferences/{user_id}")
async def get_preferences(user_id: str):
    """Returns the parsed long-term preferences for a specific user ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT preferences FROM user_preferences WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        import json
        return json.loads(row["preferences"])
    return {}
