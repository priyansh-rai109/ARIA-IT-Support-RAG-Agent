import json
import requests
from datetime import datetime
from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.database.connection import get_db_connection

def save_message(user_id: str, role: str, content: str):
    """Saves a message to the SQLite conversation history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO conversations (user_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (user_id, role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_history(user_id: str, limit: int = 8):
    """Retrieves the recent conversation history in OpenAI dict format."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Rows are ordered DESC, reverse to maintain chronological order
    history = [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
    return history

def get_user_preferences(user_id: str) -> dict:
    """Retrieves the parsed user preferences JSON dict."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT preferences FROM user_preferences WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["preferences"])
        except Exception:
            return {}
    return {}

def save_user_preferences(user_id: str, preferences: dict):
    """Saves the user preferences JSON dict."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_preferences (user_id, preferences, last_updated)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            preferences=excluded.preferences,
            last_updated=excluded.last_updated
    """, (user_id, json.dumps(preferences), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def extract_and_save_preferences(user_id: str, user_message: str, assistant_response: str):
    """Asynchronously extracts preferences from exchange and updates database."""
    if not GROQ_API_KEY:
        return
        
    system_prompt = """You are a user preference extractor. Read the conversation exchange and output a clean JSON object containing any newly declared or updated user configurations, environment preferences, default settings, hardware models, or recurring requirements.
DO NOT include general chatter. Only extract actionable IT-related configurations.
If no preferences are found, output an empty JSON object {}.
Example output: {"os_platform": "macOS", "preferred_editor": "VS Code"}"""
    
    user_prompt = f"User: {user_message}\nAssistant: {assistant_response}"
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant", # Using a fast model for preference extraction
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            },
            timeout=5
        )
        if response.status_code == 200:
            extracted = response.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
            new_prefs = json.loads(extracted)
            if new_prefs:
                current_prefs = get_user_preferences(user_id)
                current_prefs.update(new_prefs)
                save_user_preferences(user_id, current_prefs)
    except Exception as e:
        print(f"Error extracting preferences: {e}")

def get_relevant_tickets(query: str, limit: int = 3) -> list:
    """Performs a keyword query against the local tickets store to retrieve related issues."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Split query into words to build a basic keyword search
    words = [w.strip() for w in query.split() if len(w.strip()) > 3]
    if not words:
        # Fallback to general lookup
        cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC LIMIT ?", (limit,))
    else:
        # Build SQL search clause
        clause = " OR ".join(["title LIKE ?" or "description LIKE ?" for _ in words])
        # We need two parameters per word (one for title, one for description)
        params = []
        sql_clause_parts = []
        for w in words:
            sql_clause_parts.append("(title LIKE ? OR description LIKE ?)")
            params.append(f"%{w}%")
            params.append(f"%{w}%")
        
        sql_query = f"SELECT * FROM tickets WHERE {' OR '.join(sql_clause_parts)} ORDER BY created_at DESC LIMIT {limit}"
        cursor.execute(sql_query, params)
        
    rows = cursor.fetchall()
    conn.close()
    
    tickets = []
    for row in rows:
        tickets.append({
            "ticket_id": row["ticket_id"],
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "category": row["category"],
            "priority": row["priority"],
            "created_at": row["created_at"]
        })
    return tickets
