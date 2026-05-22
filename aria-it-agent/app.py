import os
import json
import base64
import urllib.parse
import gradio as gr
from datetime import datetime
from dotenv import load_dotenv
import requests
import threading

# Load env variables
load_dotenv()

# Import new modular backend services
from backend.config import SOURCES_DIR
from backend.database.connection import init_db, seed_tickets_if_empty
from backend.services.ingestion import enqueue_document, get_vectorstore
from backend.services.memory import (
    save_message,
    get_history,
    get_user_preferences,
    extract_and_save_preferences,
    get_relevant_tickets
)
from backend.services.rag_pipeline import retrieve_hybrid_context, rebuild_bm25_index

api_key = None

IT_KNOWLEDGE_BASE = [
    {"id": "RB-1001", "title": "Password Reset Policy", "category": "Security", "content": "Employees can reset passwords via the Self-Service Portal at portal.company.com. Passwords must be 12+ characters. Passwords expire every 90 days. After 5 failed attempts, accounts are locked for 30 minutes."},
    {"id": "RB-1002", "title": "VPN Setup", "category": "Network", "content": "Download GlobalProtect VPN from software.company.com/vpn. Use your Active Directory credentials. Connect before accessing internal resources."},
    {"id": "RB-1003", "title": "Software Installation", "category": "Software", "content": "Only approved software may be installed. Submit requests via the IT portal. Approved: Microsoft Office, Slack, Zoom, Chrome, VS Code, Python, Git."},
    {"id": "RB-1004", "title": "Hardware Request", "category": "Hardware", "content": "Submit hardware requests via IT Portal. SLA: 3-5 business days. Standard kit: laptop, monitor, keyboard, mouse, headset."},
    {"id": "RB-1005", "title": "IT Helpdesk", "category": "Support", "content": "Helpdesk: helpdesk@company.com or ext. 1234. Hours: Mon-Fri 8am-6pm. Critical issues: call IT Emergency line 24/7."},
    {"id": "RB-1006", "title": "MFA Setup", "category": "Security", "content": "MFA required for all corporate accounts. Use Microsoft Authenticator. Enroll at mfa.company.com. Report lost MFA device to IT immediately."},
    {"id": "RB-1007", "title": "Data Backup", "category": "Data", "content": "OneDrive auto-syncs desktop and documents. Local drives are NOT backed up. File recovery up to 30 days via OneDrive version history."},
]

def get_robot_base64():
    paths = [
        "assets/robot.png",
        "/Users/divyanshrai/ARIA IT Support RAG Agent /aria-it-agent/assets/robot.png",
        "/Users/divyanshrai/ARIA IT Support RAG Agent/aria-it-agent/robot_custom.png",
        "/Users/divyanshrai/ARIA IT Support RAG Agent/aria-it-agent/robot_new.png",
        "/Users/divyanshrai/ARIA IT Support RAG Agent/aria-it-agent/robot_v5.png",
        "robot_custom.png",
        "robot_new.png",
        "robot_v5.png"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                print(f"Error reading path {p}: {e}")
    return ""

def _slugify(text):
    return "".join(c if c.isalnum() else "_" for c in text).strip("_")

def pdf_filename_for(item):
    return f"{item['id']}_{_slugify(item['title'])}.pdf"

def pdf_path_for(item):
    return os.path.join(SOURCES_DIR, pdf_filename_for(item))

def generate_source_pdfs():
    """Generate a styled PDF for every KB entry so the UI source cards have
    real files to link to. Idempotent: skips entries whose PDFs already exist."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_LEFT
    except ImportError:
        print("reportlab not installed; source PDFs will not be generated.")
        return

    os.makedirs(SOURCES_DIR, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("AriaTitle", parent=styles["Heading1"], textColor=HexColor("#1e293b"), fontSize=22, spaceAfter=6, alignment=TA_LEFT)
    tag_style = ParagraphStyle("AriaTag", parent=styles["Normal"], textColor=HexColor("#2563eb"), fontSize=10, spaceAfter=2)
    meta_style = ParagraphStyle("AriaMeta", parent=styles["Normal"], textColor=HexColor("#64748b"), fontSize=9, spaceAfter=18)
    body_style = ParagraphStyle("AriaBody", parent=styles["BodyText"], textColor=HexColor("#0f172a"), fontSize=12, leading=18, spaceAfter=12)
    footer_style = ParagraphStyle("AriaFooter", parent=styles["Normal"], textColor=HexColor("#94a3b8"), fontSize=8, alignment=TA_LEFT)

    for item in IT_KNOWLEDGE_BASE:
        out_path = pdf_path_for(item)
        if os.path.exists(out_path):
            continue
        try:
            doc = SimpleDocTemplate(out_path, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch, topMargin=0.9 * inch, bottomMargin=0.9 * inch, title=item["title"], author="ARIA IT Support")
            story = [
                Paragraph(f"<b>{item['id']}</b>  ·  {item['category'].upper()}", tag_style),
                Paragraph(item["title"], title_style),
                Paragraph(f"ARIA Knowledge Base · Generated {datetime.now().strftime('%Y-%m-%d')}", meta_style),
                Paragraph(item["content"].replace("\n", "<br/>"), body_style),
                Spacer(1, 0.4 * inch),
                Paragraph("This document is auto-generated from the ARIA IT knowledge base. For the latest version, consult the Self-Service Portal.", footer_style),
            ]
            doc.build(story)
        except Exception as e:
            print(f"Failed to generate PDF for {item.get('id')}: {e}")

def seed_chroma_if_empty():
    """Seeds the Chroma DB with default Knowledge Base items if it is currently empty."""
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    try:
        vectorstore = get_vectorstore()
        res = vectorstore.get()
        if not res.get("documents"):
            print("Chroma DB is empty. Seeding with default knowledge base...")
            generate_source_pdfs()
            documents = [
                Document(
                    page_content=item["content"],
                    metadata={
                        "id": item["id"],
                        "title": item["title"],
                        "category": item["category"],
                        "pdf": pdf_filename_for(item)
                    }
                )
                for item in IT_KNOWLEDGE_BASE
            ]
            splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
            chunks = splitter.split_documents(documents)
            vectorstore.add_documents(chunks)
            print("Chroma DB seeded successfully!")
            
            # Trigger BM25 rebuild to keep synchronized
            rebuild_bm25_index()
    except Exception as e:
        print(f"Error seeding Chroma: {e}")

def initialize_system():
    global api_key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return False, "GROQ_API_KEY not found in .env file."
    try:
        init_db()
        seed_tickets_if_empty()
        seed_chroma_if_empty()
        return True, "ARIA Enterprise initialized successfully with Groq and SQLite!"
    except Exception as e:
        return False, f"Initialization error: {e}"

def handle_file_upload(file_obj):
    if file_obj is None:
        return "No file selected."
    try:
        if isinstance(file_obj, list):
            results = []
            for f in file_obj:
                file_path = f.name if hasattr(f, "name") else str(f)
                file_name = os.path.basename(file_path)
                with open(file_path, "rb") as file_bytes:
                    res = enqueue_document(file_name, file_bytes.read())
                    results.append(res["message"])
            return "\n".join(results)
        else:
            file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as file_bytes:
                res = enqueue_document(file_name, file_bytes.read())
                return res["message"]
    except Exception as e:
        return f"Upload error: {str(e)}"

def get_ingestion_status_html():
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingestion_status ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return """
        <div style='text-align:center; padding:16px; color:var(--muted); font-size:12px; border:1px dashed var(--border); border-radius:12px; background:var(--bg-soft);'>
            No files ingested yet. Drag & drop files above.
        </div>
        """
        
    html = """
    <div style='display:flex; flex-direction:column; gap:6px;'>
    """
    for r in rows:
        status = r["status"]
        progress = r["progress"]
        if status == "Complete":
            color = "var(--success)"
            bg = "rgba(52, 211, 153, 0.1)"
        elif status == "Failed":
            color = "var(--danger)"
            bg = "rgba(248, 113, 113, 0.1)"
        else:
            color = "var(--accent)"
            bg = "rgba(99, 102, 241, 0.1)"
            
        try:
            time_str = datetime.fromisoformat(r["timestamp"]).strftime('%b %d, %H:%M')
        except Exception:
            time_str = r["timestamp"]
            
        html += f"""
        <div style='background:var(--bg-soft); border:1px solid var(--border-soft); border-radius:10px; padding:10px; display:flex; justify-content:space-between; align-items:center; gap:10px;'>
            <div style='display:flex; flex-direction:column; gap:2px; overflow:hidden; flex-grow:1;'>
                <span style='font-size:12px; font-weight:500; color:var(--text); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;'>{r["file_name"]}</span>
                <span style='font-size:10px; color:var(--muted);'>{time_str}</span>
            </div>
            <div style='display:flex; flex-direction:column; align-items:flex-end; gap:2px; flex-shrink:0;'>
                <span style='font-size:10px; font-weight:600; padding:2px 8px; border-radius:100px; background:{bg}; color:{color};'>{status} ({progress}%)</span>
                {f"<span style='font-size:9px; color:var(--danger); max-width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' title='{r['error_message']}'>{r['error_message']}</span>" if r["error_message"] else ""}
            </div>
        </div>
        """
    html += "</div>"
    return html

def get_tickets_html():
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    html = """
    <div style='display:flex; flex-direction:column; gap:8px;'>
    """
    for r in rows:
        status_color = "var(--success)" if r["status"] == "Resolved" else ("var(--accent)" if r["status"] == "In Progress" else "var(--danger)")
        priority_bg = "rgba(248, 113, 113, 0.15)" if r["priority"] in ["High", "Critical"] else "rgba(156, 163, 175, 0.15)"
        priority_color = "var(--danger)" if r["priority"] in ["High", "Critical"] else "var(--muted)"
        
        html += f"""
        <div style='background:var(--bg-soft); border:1px solid var(--border-soft); border-radius:12px; padding:12px; display:flex; flex-direction:column; gap:6px;'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <span style='font-size:11px; font-weight:700; color:var(--accent);'>{r["ticket_id"]}</span>
                <span style='font-size:10px; font-weight:600; padding:2px 8px; border-radius:100px; background:{priority_bg}; color:{priority_color};'>{r["priority"]}</span>
            </div>
            <div style='font-weight:600; font-size:13px; color:var(--text);'>{r["title"]}</div>
            <div style='font-size:11px; color:var(--muted); line-height:1.4;'>{r["description"] or ""}</div>
            <div style='display:flex; justify-content:space-between; align-items:center; margin-top:4px; border-top:1px solid rgba(255,255,255,0.03); padding-top:6px;'>
                <span style='font-size:10px; color:var(--muted);'>{r["category"]}</span>
                <span style='font-size:11px; color:{status_color}; font-weight:600; display:flex; align-items:center; gap:4px;'>
                    <span style='width:6px; height:6px; background:{status_color}; border-radius:50%; display:inline-block; box-shadow: 0 0 6px {status_color};'></span>
                    {r["status"]}
                </span>
            </div>
        </div>
        """
    html += "</div>"
    return html

def get_preferences_html():
    from backend.services.memory import get_user_preferences
    prefs = get_user_preferences("default_user")
    
    if not prefs:
        return """
        <div style='text-align:center; padding:20px; color:var(--muted); font-size:12px; border:1px dashed var(--border); border-radius:12px; background:var(--bg-soft);'>
            <span>🧠</span> Memory is empty. Conversing with ARIA will automatically extract user preferences.
        </div>
        """
    
    html = """
    <div style='display:flex; flex-wrap:wrap; gap:8px;'>
    """
    for k, v in prefs.items():
        label = k.replace("_", " ").title()
        html += f"""
        <div style='background:rgba(99, 102, 241, 0.08); border:1px solid rgba(99, 102, 241, 0.25); border-radius:10px; padding:8px 12px; display:flex; flex-direction:column; gap:2px; flex-grow:1; min-width:120px;'>
            <span style='font-size:10px; color:var(--muted); font-weight:500;'>{label}</span>
            <span style='font-size:12px; color:var(--accent); font-weight:600;'>{v}</span>
        </div>
        """
    html += "</div>"
    return html

def handle_create_ticket_action():
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    ticket_id = f"IT-{1487 + count}"
    cursor.execute("""
        INSERT INTO tickets (ticket_id, title, description, status, category, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id,
        "User Requested Escalation Ticket",
        "Autonomous ticket generated via ARIA Suggested Action shortcut.",
        "Open",
        "Support",
        "High",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return [{"role": "user", "content": f"I have created a new high-priority support ticket {ticket_id} for you. Can you help me track it?"}]

def handle_page_infra_action():
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    ticket_id = f"IT-{1487 + count}"
    cursor.execute("""
        INSERT INTO tickets (ticket_id, title, description, status, category, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id,
        "Infrastructure Team On-Call Paging",
        "Automated alert paging sent to #infra-oncall.",
        "Open",
        "Network",
        "Critical",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return [{"role": "user", "content": f"I have paged the Infrastructure Team (#infra-oncall) under ticket {ticket_id} regarding the active alert."}]

def handle_security_escalation_action():
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0]
    ticket_id = f"IT-{1487 + count}"
    cursor.execute("""
        INSERT INTO tickets (ticket_id, title, description, status, category, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id,
        "High Priority Security Escalation",
        "Security incident report escalated to standard Security Response team.",
        "Open",
        "Security",
        "Critical",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
    return [{"role": "user", "content": f"Security escalation initiated. Ticket {ticket_id} created with Critical priority."}]

def stream_response(message, history):
    global api_key
    if not api_key:
        ok, msg = initialize_system()
        if not ok:
            yield msg
            return

    user_id = "default_user"

    # 1. Retrieve history (Short-term Context) BEFORE saving the current user message
    db_history = get_history(user_id, limit=6)

    # 2. Save user message to database
    save_message(user_id, "user", message)

    # 3. Retrieve grounding data (Hybrid RAG + SQLite Tickets + User Preferences)
    context_text, sources = retrieve_hybrid_context(message)
    related_tickets = get_relevant_tickets(message)
    user_prefs = get_user_preferences(user_id)

    # 4. Formulate robust Enterprise System Prompt
    system_instruction = (
        "You are ARIA, a highly skilled Enterprise IT Support and Autonomous Operations AI.\n"
        f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    )

    if user_prefs:
        system_instruction += f"USER PREFERENCES (Remembered Configurations):\n{json.dumps(user_prefs, indent=2)}\n\n"

    if context_text:
        system_instruction += f"KNOWLEDGE BASE GROUNDING:\n{context_text}\n\n"

    if related_tickets:
        ticket_desc = "\n".join([f"- [{t['ticket_id']}] {t['title']} (Status: {t['status']}, Priority: {t['priority']})" for t in related_tickets])
        system_instruction += f"RELATED HISTORICAL TICKETS:\n{ticket_desc}\n\n"

    system_instruction += (
        "Answer the user's issue concisely, professionally, and accurately using the provided grounding data.\n"
        "If related historical tickets are found, proactively mention them to help resolve recurring issues."
    )

    # Assemble API message structure
    api_messages = [{"role": "system", "content": system_instruction}]
    for turn in db_history:
        api_messages.append({"role": turn["role"], "content": turn["content"]})
    api_messages.append({"role": "user", "content": message})

    # Stream from Groq API
    answer = ""
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": api_messages, "stream": True},
            stream=True
        )

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    data_payload = line_str[6:]
                    if data_payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_payload)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            answer += delta
                            yield answer
                    except:
                        pass

        # Save assistant response to DB (save only clean text, no HTML cards pollution)
        save_message(user_id, "assistant", answer)

        # Asynchronously trigger user preference extraction in background thread
        threading.Thread(
            target=extract_and_save_preferences,
            args=(user_id, message, answer),
            daemon=True
        ).start()

        # Sources clickable cards
        if sources:
            unique_count = len({f"{s['title']} ({s['category']})" for s in sources})
            cards_html = (
                f"<div class='aria-sources-title'>Sources ({unique_count})</div>"
                "<div class='aria-sources-grid'>"
            )
            seen_sources = set()
            for s in sources:
                source_str = f"{s['title']} ({s['category']})"
                if source_str in seen_sources:
                    continue
                seen_sources.add(source_str)
                pdf_name = s.get("pdf", "")
                source_id = s.get("id", "")
                pdf_url = f"/gradio_api/file=sources/{urllib.parse.quote(pdf_name)}" if pdf_name else "#"
                cards_html += (
                    f"<a class='aria-source-card' href='{pdf_url}' target='_blank' rel='noopener noreferrer' title='Open {s['title']} (PDF)'>"
                    "<div class='aria-source-card-title'>"
                    "<span class='aria-source-card-icon'>📄</span>"
                    f"<span>{s['title']}<br>({s['category']})</span>"
                    "</div>"
                    f"<div class='aria-source-card-tag'>{source_id}</div>"
                    "</a>"
                )
            cards_html += "</div>"
            yield answer + "\n\n" + cards_html
        else:
            yield answer

    except Exception as e:
        yield f"Error: {str(e)}"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
  --bg: #090d16;
  --bg-soft: #111827;
  --card: #1f2937;
  --border: #2d3748;
  --border-soft: #1f2937;
  --accent: #818cf8;          /* Indigo-400 */
  --accent-strong: #6366f1;   /* Indigo-500 */
  --accent2: #a78bfa;          /* Violet-400 */
  --accent3: #2dd4bf;          /* Teal-400 */
  --success: #34d399;          /* Emerald-400 */
  --danger: #f87171;           /* Red-400 */
  --text: #f3f4f6;             /* Gray-100 */
  --text-soft: #e5e7eb;        /* Gray-200 */
  --muted: #9ca3af;            /* Gray-400 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 12px 30px rgba(99, 102, 241, 0.15), 0 4px 12px rgba(0, 0, 0, 0.4);
}
body, .gradio-container { background-color: var(--bg) !important; background-image: radial-gradient(circle at 0% 0%, rgba(99, 102, 241, 0.12) 0%, transparent 50%), radial-gradient(circle at 100% 0%, rgba(20, 184, 166, 0.12) 0%, transparent 50%) !important; font-family: 'Inter', sans-serif !important; color: var(--text) !important; min-height: 100vh; margin: 0; padding: 0; }
.gradio-container { max-width: 1400px !important; margin: 0 auto !important; padding: 24px !important; }
h1, h2, h3, .space-font { font-family: 'Inter', sans-serif !important; color: var(--text); }
* { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }

.navbar { background: transparent !important; display: flex; align-items: center; padding: 8px 0 28px 0; gap: 24px; position: sticky; top: 0; z-index: 100; }
.logo-circle { width: 44px; height: 44px; border-radius: 14px; background: linear-gradient(135deg, var(--accent), var(--accent2)); border: none; display: flex; align-items: center; justify-content: center; box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35); }
.logo-inner { font-size: 20px; color: #fff; }
.metrics-container { display: flex; gap: 14px; margin-left: 20px; flex-grow: 1; }
.metric-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 12px 16px; display: flex; align-items: center; gap: 24px; width: 170px; box-shadow: var(--shadow-sm); transition: transform 0.18s ease, box-shadow 0.18s ease; }
.metric-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.metric-card-content { display: flex; flex-direction: column; }
.metric-value { font-size: 22px; font-weight: 700; color: var(--text); display: flex; align-items: baseline; gap: 6px; letter-spacing: -0.01em; }
.metric-value-up { font-size: 11px; color: var(--success); font-weight: 600; }
.metric-label { font-size: 11px; color: var(--muted); margin-bottom: 2px; font-weight: 500; }
.metric-icon { opacity: 0.85; font-size: 20px; margin-left: auto; }
.online-badge { background: rgba(16, 185, 129, 0.10); border: 1px solid rgba(16, 185, 129, 0.25); color: var(--success); padding: 8px 16px; border-radius: 100px; font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 8px; margin-left: auto; }
.online-dot { width: 6px; height: 6px; background: var(--success); border-radius: 50%; box-shadow: 0 0 8px var(--success); }

.main-layout { gap: 24px; }

/* Left Sidebar */
.left-col { background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 22px; display: flex; flex-direction: column; gap: 8px; box-shadow: var(--shadow-sm); }
.section-title { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px; margin-top: 16px; }
.section-title:first-child { margin-top: 0; }
.btn-glass { background: var(--bg-soft) !important; border: 1px solid var(--border-soft) !important; color: var(--text) !important; text-align: left !important; justify-content: flex-start !important; padding: 13px 16px !important; border-radius: 12px !important; font-size: 14px !important; font-weight: 500 !important; transition: all 0.18s ease !important; display: flex !important; align-items: center !important; gap: 12px !important; box-shadow: none !important; }
.btn-glass:hover { background: rgba(99, 102, 241, 0.12) !important; border-color: var(--accent) !important; color: var(--accent) !important; transform: translateY(-1px); box-shadow: var(--shadow-sm) !important; }
.btn-active { background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; border: none !important; color: #ffffff !important; text-align: left !important; justify-content: flex-start !important; padding: 13px 16px !important; border-radius: 12px !important; font-size: 14px !important; font-weight: 600 !important; display: flex !items: center !important; gap: 12px !important; box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35) !important; }
.btn-active:hover { filter: brightness(1.05); }
.it-contact { background: var(--bg-soft); border: 1px solid var(--border-soft); border-radius: 12px; padding: 14px 16px; margin-bottom: 8px; display: flex; gap: 12px; align-items: flex-start; }
.it-contact-icon { font-size: 18px; margin-top: 2px; }

/* Center Chat */
.center-col { background: var(--card); border: 1px solid var(--border); border-radius: 18px; padding: 24px; display: flex; flex-direction: column; box-shadow: var(--shadow-sm); }
#chatbot { background: transparent !important; border: none !important; }
#chatbot .message-row, #chatbot .message { font-size: 14px !important; line-height: 1.65 !important; }
#chatbot .message { padding: 14px 18px !important; border-radius: 14px !important; }
#chatbot .user .message, #chatbot [data-testid='user'] .message, #chatbot .user-row .message { background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; color: #ffffff !important; border-radius: 16px 16px 4px 16px !important; box-shadow: 0 6px 18px rgba(99, 102, 241, 0.25) !important; border: none !important; max-width: 80% !important; }
#chatbot .bot .message, #chatbot [data-testid='bot'] .message, #chatbot .bot-row .message { background: var(--bg-soft) !important; border: 1px solid var(--border-soft) !important; color: var(--text) !important; border-radius: 16px 16px 16px 4px !important; max-width: 90% !important; box-shadow: var(--shadow-sm) !important; }
#chatbot .bot .message p, #chatbot .bot .message li, #chatbot .bot .message span, #chatbot [data-testid='bot'] .message p, #chatbot [data-testid='bot'] .message li, #chatbot [data-testid='bot'] .message span { color: var(--text) !important; }
#chatbot .bot .message a, #chatbot [data-testid='bot'] .message a { color: var(--accent) !important; text-decoration: underline; }
#chatbot .bot .message code, #chatbot [data-testid='bot'] .message code { background: rgba(99,102,241,0.15) !important; color: var(--accent) !important; padding: 1px 6px; border-radius: 5px; font-size: 12px; }

.chat-input-container { background: var(--bg-soft) !important; border: 1px solid var(--border-soft) !important; border-radius: 14px !important; padding: 6px !important; margin-top: 24px !important; align-items: center !important; transition: border-color 0.2s ease, box-shadow 0.2s ease; }
.chat-input-container:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12) !important; background: var(--bg-soft) !important; }
.chat-input, .chat-input > div, .chat-input .form, .chat-input .wrap, .chat-input .container, .chat-input .input-container { background: transparent !important; border: none !important; box-shadow: none !important; }
.chat-input input, .chat-input textarea { background: transparent !important; border: none !important; color: var(--text) !important; font-size: 14px !important; box-shadow: none !important; padding: 12px !important; outline: none !important; -webkit-text-fill-color: var(--text) !important; caret-color: var(--accent) !important; }
.chat-input input::placeholder, .chat-input textarea::placeholder { color: var(--muted) !important; opacity: 1 !important; }
.chat-input input:focus, .chat-input textarea:focus { border: none !important; box-shadow: none !important; outline: none !important; }
.chat-input input:-webkit-autofill, .chat-input textarea:-webkit-autofill { -webkit-box-shadow: 0 0 0 30px var(--bg-soft) inset !important; -webkit-text-fill-color: var(--text) !important; caret-color: var(--accent) !important; }
.send-btn { background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; border: none !important; color: #ffffff !important; border-radius: 10px !important; width: 44px !important; height: 44px !important; min-width: unset !important; padding: 0 !important; display: flex !important; justify-content: center !important; align-items: center !important; box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35) !important; transition: transform 0.15s ease, filter 0.15s ease !important; }
.send-btn:hover { transform: translateY(-1px); filter: brightness(1.06); }

/* Right Panel */
.right-col { background: transparent; padding: 0; display: flex; flex-direction: column; gap: 16px; }
.robot-img { border-radius: 18px; box-shadow: var(--shadow-lg); border: 1px solid var(--border); width: 100%; display: block; margin-bottom: 0; background: var(--bg-soft); }
.thinking-card { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 14px; padding: 12px 20px; display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow-md); font-size: 14px; font-weight: 500; color: var(--text); margin-top: -20px; z-index: 10; position: relative; width: 90%; margin-left: 5%; }
.thinking-dots { display: flex; gap: 4px; margin-left: auto; }
.thinking-dots div { width: 6px; height: 6px; background: var(--accent); border-radius: 50%; animation: blink 1.4s infinite both; }
.thinking-dots div:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots div:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0% { opacity: 0.2; } 20% { opacity: 1; } 100% { opacity: 0.2; } }

.suggested-actions { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 18px !important; padding: 22px !important; flex-grow: 1 !important; box-shadow: var(--shadow-sm); }
.suggested-actions * { background: transparent !important; color: var(--text) !important; }
.action-btn { background: transparent !important; border: none !important; border-bottom: 1px solid var(--border-soft) !important; border-radius: 0 !important; padding: 14px 0 !important; display: flex !important; align-items: center !important; gap: 12px !important; text-align: left !important; color: var(--text) !important; font-size: 14px !important; font-weight: 500 !important; justify-content: flex-start !important; box-shadow: none !important; cursor: pointer; transition: all 0.18s ease; }
.action-btn:last-child { border-bottom: none !important; }
.action-btn:hover { background: var(--bg-soft) !important; padding-left: 8px !important; padding-right: 8px !important; border-radius: 10px !important; }
.action-icon { font-size: 18px; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: var(--bg); }
.action-text { display: flex; flex-direction: column; flex-grow: 1; }
.action-subtext { font-size: 11px; color: var(--muted) !important; margin-top: 2px; }
.action-arrow { margin-left: auto; color: var(--muted) !important; font-size: 18px; }
#hidden-actions-container { display: none !important; }
footer { display: none !important; }

/* Scrollbar polish */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 10px; border: 2px solid var(--bg); }
::-webkit-scrollbar-thumb:hover { background: #4b5563; }

/* Source cards rendered inside Chatbot messages (class-based to survive Gradio HTML sanitization) */
.aria-sources-title { font-size: 12px; color: var(--accent); margin-top: 20px; margin-bottom: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; }
.aria-sources-grid { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 4px; border-top: 1px solid var(--border-soft); padding-top: 14px; }
.aria-source-card { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 12px; padding: 14px; width: 168px; display: flex; flex-direction: column; gap: 8px; text-decoration: none !important; color: inherit !important; cursor: pointer; transition: all 0.18s ease; box-shadow: var(--shadow-sm); }
.aria-source-card:hover { background: var(--card) !important; border-color: var(--accent) !important; transform: translateY(-2px); box-shadow: 0 10px 24px rgba(99, 102, 241, 0.25); }
.aria-source-card-title { font-size: 12px; font-weight: 600; color: var(--text) !important; display: flex; gap: 6px; align-items: flex-start; line-height: 1.45; }
.aria-source-card-icon { color: var(--accent); font-size: 14px; }
.aria-source-card-tag { font-size: 10px; color: var(--accent) !important; background: rgba(99, 102, 241, 0.15); padding: 3px 8px; border-radius: 6px; align-self: flex-start; margin-top: 2px; font-weight: 600; letter-spacing: 0.3px; }
"""

def build_ui():
    with gr.Blocks(title="ARIA Enterprise AI Operating System") as demo:
        gr.HTML("""
        <div class="navbar">
            <div class="logo-circle">
                <div class="logo-inner">⚡</div>
            </div>
            <div>
                <div class="space-font" style="font-size: 22px; font-weight: 800; letter-spacing: -0.5px; color: var(--text);">ARIA</div>
                <div style="font-size: 11px; color: var(--muted); letter-spacing: 0.4px; font-weight: 500;">Enterprise AI Operating System · <span style="color:var(--accent-strong); font-weight:600;">Hybrid RAG Active</span></div>
            </div>
            <div class="metrics-container">
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">Active Tickets</span>
                        <span class="metric-value">24 <span class="metric-value-up">▲ 12%</span></span>
                    </div>
                    <div class="metric-icon" style="color:var(--accent);">🎫</div>
                </div>
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">Security Alerts</span>
                        <span class="metric-value">2 <span class="metric-value-up" style="color:var(--danger);">▲ 100%</span></span>
                    </div>
                    <div class="metric-icon" style="color:var(--danger);">🛡️</div>
                </div>
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">AI Status</span>
                        <span class="metric-value" style="color:var(--success);">Online</span>
                        <span style="font-size:10px; color:var(--muted); margin-top:-4px;">Groq Connected</span>
                    </div>
                    <div class="metric-icon" style="color:var(--accent3);">🌐</div>
                </div>
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">Ensemble Search</span>
                        <span class="metric-value" style="color:var(--accent3);">Active</span>
                        <span style="font-size:10px; color:var(--success); margin-top:-4px;">RRF + BM25</span>
                    </div>
                    <div class="metric-icon" style="color:var(--accent2);">⏱️</div>
                </div>
            </div>
            <div class="online-badge">
                <div class="online-dot"></div> ARIA Online
            </div>
        </div>
        """)
        
        with gr.Row(elem_classes="main-layout"):
            # Left Sidebar
            with gr.Column(scale=20, min_width=250, elem_classes="left-col"):
                gr.HTML("<div class='section-title'>QUICK ACTIONS</div>")
                btn1 = gr.Button("🔑 Password Reset", elem_classes="btn-active")
                btn2 = gr.Button("🌐 VPN Setup", elem_classes="btn-glass")
                btn3 = gr.Button("📁 Recover Files", elem_classes="btn-glass")
                btn4 = gr.Button("🔒 Setup MFA", elem_classes="btn-glass")
                
                gr.HTML("<div class='section-title'>DOCUMENT INGESTION</div>")
                uploader = gr.File(label="Upload Knowledge Document", file_types=[".txt", ".pdf", ".docx", ".pptx", ".csv"], type="filepath", elem_classes="btn-glass")
                upload_message = gr.Markdown(value="", elem_classes="action-subtext")
                
                with gr.Row():
                    gr.HTML("<div class='section-title'>INGESTION STATUS</div>", scale=8)
                    refresh_ingestion_btn = gr.Button("🔄", size="sm", elem_classes="btn-glass", scale=2)
                ingestion_display = gr.HTML(value=get_ingestion_status_html())
                
                gr.HTML("<div class='section-title'>IT CONTACTS</div>")
                gr.HTML("""
                <div class='it-contact'>
                    <div class='it-contact-icon'>✉️</div>
                    <div style='flex-grow:1;'>
                        <div style='font-weight:600;font-size:13px;color:var(--text); display:flex; justify-content:space-between; align-items:center; width:100%;'>Helpdesk <span style='width:6px;height:6px;background:var(--success);border-radius:50%;display:inline-block;box-shadow:0 0 6px var(--success);'></span></div>
                        <div style='font-size:11px;color:var(--muted);margin-top:2px;line-height:1.5;'>helpdesk@company.com<br>Ext. 1234 · Mon–Fri 8am–6pm</div>
                    </div>
                </div>
                <div class='it-contact'>
                    <div class='it-contact-icon'>📞</div>
                    <div style='flex-grow:1;'>
                        <div style='font-weight:600;font-size:13px;color:var(--text); display:flex; justify-content:space-between; align-items:center; width:100%;'>Emergency (24/7) <span style='width:6px;height:6px;background:var(--danger);border-radius:50%;display:inline-block;box-shadow:0 0 6px var(--danger);'></span></div>
                        <div style='font-size:11px;color:var(--muted);margin-top:2px;'>Ext. 9911</div>
                    </div>
                </div>
                """)
                sys_status = gr.Button("📊 System Status >", elem_classes="btn-glass")

            # Center Column (Chatbot)
            with gr.Column(scale=50, min_width=500, elem_classes="center-col"):
                gr.HTML("<div style='display:flex; align-items:center; gap:8px; font-weight:700; font-size:14px; margin-bottom:16px;'><span style='display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:8px; background:linear-gradient(135deg, var(--accent), var(--accent2)); color:white; font-size:12px;'>A</span><span style='color:var(--text);'>ARIA</span><span style='font-size:11px; color:var(--muted); font-weight:500; margin-left:4px;'>· Conversational IT assistant</span></div>")
                chatbot = gr.Chatbot(elem_id="chatbot", height=500, show_label=False, avatar_images=(None, "https://api.iconify.design/ri:robot-2-fill.svg?color=%236366f1"))
                with gr.Row(elem_classes="chat-input-container"):
                    msg = gr.Textbox(placeholder="Ask me anything about IT support...", show_label=False, scale=10, elem_classes="chat-input", container=False)
                    send = gr.Button("➤", scale=1, elem_classes="send-btn")
                
                gr.HTML("""
                <div style='text-align:center; padding-top:8px; font-size:10px; color:var(--muted);'>
                    ARIA may make mistakes. Verify important information.
                </div>
                <div style='display:flex;justify-content:space-between;padding:16px 0 0 0;font-size:11px;color:var(--muted); border-top:1px solid var(--border-soft); margin-top:16px;'>
                    <div style='display:flex; gap:16px;'>
                        <span><span style='color:var(--success);'>●</span> Hybrid RAG: Active</span>
                        <span><span style='color:var(--success);'>●</span> SQLite Memory: Persistent</span>
                        <span><span style='color:var(--success);'>●</span> Model: llama-3.3-70b-versatile</span>
                    </div>
                    <div style='cursor:pointer; display:flex; align-items:center; gap:4px; color:var(--muted);' onclick="document.querySelector('#clear-btn').click()"><span style='font-size:14px;'>🗑️</span> Clear Chat</div>
                </div>
                """)
                clear = gr.Button("Clear", elem_id="clear-btn", visible=False)

            # Right Column (Information & Dashboards)
            with gr.Column(scale=30, min_width=300, elem_classes="right-col"):
                robot_b64 = get_robot_base64()
                if robot_b64:
                    gr.HTML(f'<img src="data:image/png;base64,{robot_b64}" class="robot-img" alt="ARIA Robot Mascot">')
                else:
                    gr.HTML('<div class="robot-img" style="height: 300px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg, rgba(99,102,241,0.08), rgba(20,184,166,0.08)); border:1px dashed var(--border); border-radius:18px; color:var(--muted); font-size:32px;">🤖</div>')
                
                gr.HTML("""
                <div class="thinking-card">
                    <span>🧠</span>
                    <span>ARIA is analyzing...</span>
                    <div class="thinking-dots"><div></div><div></div><div></div></div>
                </div>
                """)
                
                with gr.Group(elem_classes="suggested-actions"):
                    with gr.Row():
                        gr.HTML("<div class='section-title'>ARIA MEMORY VAULT</div>", scale=8)
                        refresh_memory_btn = gr.Button("🔄", size="sm", elem_classes="btn-glass", scale=2)
                    memory_display = gr.HTML(value=get_preferences_html())
                    
                with gr.Group(elem_classes="suggested-actions"):
                    with gr.Row():
                        gr.HTML("<div class='section-title'>LIVE TICKET REGISTRY</div>", scale=8)
                        refresh_tickets_btn = gr.Button("🔄", size="sm", elem_classes="btn-glass", scale=2)
                    tickets_display = gr.HTML(value=get_tickets_html())

                with gr.Group(elem_classes="suggested-actions"):
                    gr.HTML("<div class='section-title'>SUGGESTED ACTIONS</div>")
                    with gr.Column(elem_id="hidden-actions-container"):
                        btn_jira = gr.Button("Create Jira", elem_id="btn-jira")
                        btn_infra = gr.Button("Page Infra", elem_id="btn-infra")
                        btn_email = gr.Button("Send Email", elem_id="btn-email")
                        btn_security = gr.Button("Security Escalation", elem_id="btn-security")
                    gr.HTML("""
                    <button class='action-btn' onclick="document.getElementById('btn-jira').click()">
                        <div class='action-icon' style='color:var(--accent);'>🎫</div>
                        <div class='action-text'>Create Jira Ticket<span class='action-subtext'>IT-1487</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    <button class='action-btn' onclick="document.getElementById('btn-infra').click()">
                        <div class='action-icon' style='color:var(--accent2);'>🔔</div>
                        <div class='action-text'>Page Infrastructure Team<span class='action-subtext'>#infra-oncall</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    <button class='action-btn' onclick="document.getElementById('btn-email').click()">
                        <div class='action-icon' style='color:var(--accent3);'>✉️</div>
                        <div class='action-text'>Send Email to User<span class='action-subtext'>user@company.com</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    <button class='action-btn' onclick="document.getElementById('btn-security').click()">
                        <div class='action-icon' style='color:var(--danger);'>🛡️</div>
                        <div class='action-text'>Security Escalation<span class='action-subtext' style='color:var(--danger);'>High Priority</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    """)

        chat_history = gr.State([
            {"role": "user", "content": "How do I reset my password?"}, 
            {"role": "assistant", "content": "You can reset your password via the Self-Service Portal at portal.company.com.\n\nEnsure your new password is 12+ characters long. If you have any issues, feel free to ask."}
        ])

        def user_submit(message, history):
            if not message.strip():
                return "", history
            return "", history + [{"role": "user", "content": message}]

        def bot_respond(history):
            if not history or history[-1]["role"] != "user":
                yield history
                return
            user_msg = history[-1]["content"]
            history = history + [{"role": "assistant", "content": ""}]
            for partial in stream_response(user_msg, history[:-1]):
                history[-1]["content"] = partial
                yield history

        # Event Handlers
        msg.submit(
            user_submit, [msg, chat_history], [msg, chat_history]
        ).then(
            bot_respond, chat_history, chat_history
        ).then(
            get_preferences_html, outputs=[memory_display]
        ).then(
            get_tickets_html, outputs=[tickets_display]
        )
        
        send.click(
            user_submit, [msg, chat_history], [msg, chat_history]
        ).then(
            bot_respond, chat_history, chat_history
        ).then(
            get_preferences_html, outputs=[memory_display]
        ).then(
            get_tickets_html, outputs=[tickets_display]
        )
        
        clear.click(lambda: [], None, chat_history)
        chat_history.change(lambda h: h, chat_history, chatbot)

        # Ingestion Uploader triggers
        uploader.upload(
            handle_file_upload,
            inputs=[uploader],
            outputs=[upload_message]
        ).then(
            get_ingestion_status_html,
            outputs=[ingestion_display]
        )
        
        refresh_ingestion_btn.click(
            get_ingestion_status_html,
            outputs=[ingestion_display]
        )
        
        refresh_tickets_btn.click(
            get_tickets_html,
            outputs=[tickets_display]
        )
        
        refresh_memory_btn.click(
            get_preferences_html,
            outputs=[memory_display]
        )

        # Quick Actions & Suggested Actions Mapping
        for btn, query in [
            (btn1, "How do I reset my password?"), 
            (btn2, "Help me setup VPN"), 
            (btn3, "How to recover deleted files?"), 
            (btn4, "How to setup MFA?"),
            (sys_status, "What is the current system status and are there any active alerts?"),
            (btn_email, "Draft an email response to the user regarding their IT support issue.")
        ]:
            btn.click(
                lambda q=query: [{"role": "user", "content": q}], 
                outputs=chat_history
            ).then(
                bot_respond, chat_history, chat_history
            )

        # Autonomous shortcuts
        btn_jira.click(
            handle_create_ticket_action,
            outputs=chat_history
        ).then(
            bot_respond, chat_history, chat_history
        ).then(
            get_tickets_html, outputs=[tickets_display]
        )
        
        btn_infra.click(
            handle_page_infra_action,
            outputs=chat_history
        ).then(
            bot_respond, chat_history, chat_history
        ).then(
            get_tickets_html, outputs=[tickets_display]
        )
        
        btn_security.click(
            handle_security_escalation_action,
            outputs=chat_history
        ).then(
            bot_respond, chat_history, chat_history
        ).then(
            get_tickets_html, outputs=[tickets_display]
        )

    return demo

if __name__ == "__main__":
    print("Starting ARIA Enterprise OS...")
    
    # 1. Start the FastAPI server programmatically in a daemon thread on port 8000
    from backend.main import run_server
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 2. Run system and seeding checks
    ok, msg = initialize_system()
    print(msg)
    
    # 3. Build and launch the Gradio blocks dashboard on port 7860
    demo = build_ui()
    demo.queue()
    demo.launch(
        server_name="0.0.0.0", 
        server_port=int(os.environ.get("PORT", 7860)), 
        allowed_paths=[".", SOURCES_DIR], 
        css=CSS
    )
