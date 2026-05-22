import sqlite3
import json
from datetime import datetime
from backend.config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Conversations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL, -- 'user' or 'assistant'
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    
    # 2. User Preferences Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            preferences TEXT NOT NULL, -- JSON string
            last_updated TEXT NOT NULL
        )
    """)
    
    # 3. Tickets Table (for autonomous IT ops)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Open', -- 'Open', 'In Progress', 'Resolved'
            category TEXT,
            priority TEXT NOT NULL DEFAULT 'Medium', -- 'Low', 'Medium', 'High', 'Critical'
            created_at TEXT NOT NULL
        )
    """)
    
    # 4. Ingestion Status Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_status (
            file_name TEXT PRIMARY KEY,
            status TEXT NOT NULL, -- 'Pending', 'Processing', 'Complete', 'Failed'
            progress INTEGER DEFAULT 0,
            error_message TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # ── Part 2 New Tables ────────────────────────────────────────────────────

    # 5. Agent Memory — per-agent, per-user isolated conversation memory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # 6. Orchestrator Log — routing decisions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orchestrator_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            query TEXT NOT NULL,
            selected_agents TEXT NOT NULL, -- JSON list
            scores TEXT NOT NULL,          -- JSON dict {agent: score}
            workflow_triggered TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    # 7. Tool Executions — full audit trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL,
            params TEXT NOT NULL,          -- JSON
            agent_id TEXT,
            user_id TEXT,
            status TEXT NOT NULL,          -- 'success', 'failed', 'pending_confirmation'
            result TEXT,                   -- JSON or plain string
            error_message TEXT,
            latency_ms REAL,
            timestamp TEXT NOT NULL
        )
    """)

    # 8. Workflow States — active and completed workflow steps
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            workflow_name TEXT NOT NULL,
            user_id TEXT NOT NULL,
            current_step INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed', 'awaiting_input'
            context TEXT,                  -- JSON state carried across steps
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 9. Analytics Events — granular observability event stream
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,      -- 'retrieval', 'agent_route', 'tool_exec', 'workflow_step', 'response'
            agent_id TEXT,
            user_id TEXT,
            payload TEXT NOT NULL,         -- JSON
            latency_ms REAL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    
# Seed standard tickets if table is empty
def seed_tickets_if_empty():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    if count == 0:
        sample_tickets = [
            ("IT-1487", "VPN Access Configuration Issue", "GlobalProtect VPN failing during MFA handshake.", "Open", "Network", "High", datetime.now().isoformat()),
            ("IT-1488", "Laptop Screen Flickering", "Screen blinks on standard docking station.", "In Progress", "Hardware", "Medium", datetime.now().isoformat()),
            ("IT-1489", "Request Slack Account Creation", "New contractor starting Mon needs access.", "Resolved", "Software", "Low", datetime.now().isoformat())
        ]
        cursor.executemany("""
            INSERT INTO tickets (ticket_id, title, description, status, category, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_tickets)
        conn.commit()
    conn.close()

init_db()
seed_tickets_if_empty()
