import os
import gradio as gr
from datetime import datetime
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
import requests

load_dotenv()

vectorstore = None
api_key = None

IT_KNOWLEDGE_BASE = [
    {"title": "Password Reset Policy", "category": "Security", "content": "Employees can reset passwords via the Self-Service Portal at portal.company.com. Passwords must be 12+ characters. Passwords expire every 90 days. After 5 failed attempts, accounts are locked for 30 minutes."},
    {"title": "VPN Setup", "category": "Network", "content": "Download GlobalProtect VPN from software.company.com/vpn. Use your Active Directory credentials. Connect before accessing internal resources."},
    {"title": "Software Installation", "category": "Software", "content": "Only approved software may be installed. Submit requests via the IT portal. Approved: Microsoft Office, Slack, Zoom, Chrome, VS Code, Python, Git."},
    {"title": "Hardware Request", "category": "Hardware", "content": "Submit hardware requests via IT Portal. SLA: 3-5 business days. Standard kit: laptop, monitor, keyboard, mouse, headset."},
    {"title": "IT Helpdesk", "category": "Support", "content": "Helpdesk: helpdesk@company.com or ext. 1234. Hours: Mon-Fri 8am-6pm. Critical issues: call IT Emergency line 24/7."},
    {"title": "MFA Setup", "category": "Security", "content": "MFA required for all corporate accounts. Use Microsoft Authenticator. Enroll at mfa.company.com. Report lost MFA device to IT immediately."},
    {"title": "Data Backup", "category": "Data", "content": "OneDrive auto-syncs desktop and documents. Local drives are NOT backed up. File recovery up to 30 days via OneDrive version history."},
]

def initialize_system():
    global vectorstore, api_key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return False, "⚠️ GROQ_API_KEY not set. Please add it in your Hugging Face Space Secrets (Settings → Variables and Secrets → GROQ_API_KEY)."
    try:
        documents = [Document(page_content=item["content"], metadata={"title": item["title"], "category": item["category"]}) for item in IT_KNOWLEDGE_BASE]
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory="chroma_db")
        return True, "ARIA initialized successfully with Groq!"
    except Exception as e:
        return False, f"Vector store error: {e}"

def retrieve_context(query, k=3):
    if not vectorstore:
        return [], ""
    try:
        results = vectorstore.similarity_search_with_relevance_scores(query, k=k)
        filtered = [(doc, score) for doc, score in results if score > 0.2]
        context_parts = [f"[{doc.metadata['title']}]\n{doc.page_content}" for doc, score in filtered]
        return filtered, "\n\n".join(context_parts)
    except:
        return [], ""

def stream_response(message, history):
    global api_key
    if not api_key:
        ok, msg = initialize_system()
        if not ok:
            yield msg
            return
    retrieved_docs, context_text = retrieve_context(message)
    system_content = f"""You are ARIA, a professional IT support assistant. Be concise and helpful.
Current time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
{"KNOWLEDGE BASE:\n" + context_text if context_text else ""}"""
    messages = [{"role": "system", "content": system_content}]
    for turn in history[-6:]:
        if isinstance(turn, dict):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages, "stream": False},
        )
        data = response.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", str(data))

        if retrieved_docs:
            cards_html = "<div style='font-size: 13px; color: #3b82f6; margin-top: 20px; margin-bottom: 8px; font-weight: 600;'>Sources</div><div style='display:flex; gap:12px; flex-wrap:wrap; margin-top:5px; border-top: 1px solid rgba(255,255,255,0.05); padding-top:16px;'>"
            seen_sources = set()
            for doc, score in retrieved_docs:
                source_str = f"{doc.metadata['title']} ({doc.metadata['category']})"
                if source_str not in seen_sources:
                    cards_html += f"""
                    <div style='background:rgba(15, 23, 42, 0.4); border:1px solid rgba(59,130,246,0.15); border-radius:8px; padding:12px; width:160px; display:flex; flex-direction:column; gap:8px;'>
                        <div style='font-size:12px; font-weight:600; color:#e2e8f0; display:flex; gap:6px; align-items:flex-start;'><span style='color:#3b82f6;'>📄</span> {doc.metadata['title']}<br>({doc.metadata['category']})</div>
                        <div style='font-size:10px; color:#64748b; background:rgba(255,255,255,0.05); padding:3px 8px; border-radius:4px; align-self:flex-start; margin-top:4px;'>KB Source</div>
                    </div>
                    """
                    seen_sources.add(source_str)
            cards_html += "</div>"
            yield answer + "\n\n" + cards_html
        else:
            yield answer
    except Exception as e:
        yield f"Error: {str(e)}"

# ── Gradio 5-compatible CSS ──────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Variables ─────────────────────────────────────────────────────────────── */
:root {
  --bg: #090a0f; --card: #0c101a; --border: #1e293b;
  --accent: #4f46e5; --accent2: #2563eb; --accent3: #0ea5e9;
  --text: #f8fafc; --muted: #94a3b8;
}

/* ── Force dark background — Gradio 5 targets ──────────────────────────────── */
body, html { background: var(--bg) !important; font-family: 'Inter', sans-serif !important; }
.gradio-container {
  background: var(--bg) !important;
  background-image: radial-gradient(circle at 50% 0%, rgba(23,37,84,0.2) 0%, transparent 60%) !important;
  max-width: 1400px !important;
  margin: 0 auto !important;
  padding: 24px !important;
  min-height: 100vh;
  font-family: 'Inter', sans-serif !important;
  color: var(--text) !important;
}
/* Gradio 5 specific containers */
.app, .contain, main, .main { background: var(--bg) !important; }
.gap { background: transparent !important; }
/* Remove Gradio's default block styling */
.block, .form { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
.panel { background: transparent !important; border: none !important; }
.wrap { background: transparent !important; }
/* Remove white borders Gradio 5 adds to rows/cols */
.row { gap: 0 !important; }

/* ── Scrollbar ──────────────────────────────────────────────────────────────── */
* { scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Navbar ─────────────────────────────────────────────────────────────────── */
.navbar { background: transparent !important; display: flex; align-items: center; padding: 12px 0 32px 0; gap: 24px; }
.logo-circle { width: 44px; height: 44px; border-radius: 50%; background: #0c101a; border: 1px solid var(--accent); display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px rgba(37,99,235,0.4); flex-shrink: 0; }
.logo-inner { font-size: 20px; color: #fff; }
.metrics-container { display: flex; gap: 16px; margin-left: 20px; flex-grow: 1; flex-wrap: wrap; }
.metric-card { background: rgba(15,23,42,0.5); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 12px 16px; display: flex; align-items: center; gap: 24px; min-width: 150px; }
.metric-card-content { display: flex; flex-direction: column; }
.metric-value { font-size: 22px; font-weight: 700; color: #fff; display: flex; align-items: baseline; gap: 6px; }
.metric-value-up { font-size: 11px; color: #10b981; font-weight: 600; }
.metric-label { font-size: 11px; color: var(--muted); margin-bottom: 2px; }
.metric-icon { opacity: 0.8; font-size: 20px; margin-left: auto; }
.online-badge { border: 1px solid rgba(16,185,129,0.2); color: #10b981; padding: 8px 16px; border-radius: 100px; font-size: 11px; font-weight: 500; display: flex; align-items: center; gap: 8px; margin-left: auto; white-space: nowrap; }
.online-dot { width: 6px; height: 6px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ── Left Sidebar ──────────────────────────────────────────────────────────── */
.left-col { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 16px !important; padding: 24px !important; display: flex !important; flex-direction: column !important; gap: 8px !important; }
.section-title { font-size: 11px; font-weight: 600; color: var(--accent2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; margin-top: 16px; }
.section-title:first-child { margin-top: 0; }
/* Gradio 5 button reset */
.btn-glass { background: rgba(255,255,255,0.02) !important; border: 1px solid rgba(255,255,255,0.05) !important; color: white !important; text-align: left !important; justify-content: flex-start !important; padding: 14px 16px !important; border-radius: 12px !important; font-size: 14px !important; font-weight: 500 !important; transition: all 0.2s ease !important; display: flex !important; align-items: center !important; gap: 12px !important; box-shadow: none !important; width: 100% !important; }
.btn-glass:hover { background: rgba(255,255,255,0.06) !important; transform: translateX(2px); }
.btn-active { background: linear-gradient(90deg, #4f46e5, #7c3aed) !important; border: none !important; color: white !important; text-align: left !important; justify-content: flex-start !important; padding: 14px 16px !important; border-radius: 12px !important; font-size: 14px !important; font-weight: 500 !important; display: flex !important; align-items: center !important; gap: 12px !important; box-shadow: 0 4px 15px rgba(79,70,229,0.4) !important; width: 100% !important; }
.it-contact { background: rgba(15,23,42,0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 14px 16px; margin-bottom: 8px; display: flex; gap: 12px; align-items: flex-start; }
.it-contact-icon { font-size: 18px; margin-top: 2px; }

/* ── Center Chat Panel ─────────────────────────────────────────────────────── */
.center-col { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 16px !important; padding: 24px !important; display: flex !important; flex-direction: column !important; }

/* ── Gradio 5 Chatbot ──────────────────────────────────────────────────────── */
#chatbot { background: transparent !important; border: none !important; box-shadow: none !important; }
#chatbot .bubble-wrap { padding: 4px 0 !important; }
/* User message bubble — Gradio 5 */
#chatbot .bubble-wrap.user .bubble {
  background: linear-gradient(135deg, #2563eb, #4f46e5) !important;
  color: white !important; border-radius: 16px 16px 4px 16px !important;
  border: none !important; padding: 14px 18px !important;
  font-size: 14px !important; line-height: 1.6 !important;
  box-shadow: 0 4px 15px rgba(37,99,235,0.3) !important; max-width: 80% !important;
}
/* Bot message bubble — Gradio 5 */
#chatbot .bubble-wrap.bot .bubble {
  background: rgba(15,23,42,0.5) !important; border: 1px solid rgba(255,255,255,0.06) !important;
  color: var(--text) !important; border-radius: 4px 16px 16px 16px !important;
  padding: 14px 18px !important; font-size: 14px !important; line-height: 1.6 !important;
  max-width: 90% !important;
}
/* Also keep Gradio 4 selectors for resilience */
#chatbot .user .message { background: linear-gradient(135deg, #2563eb, #4f46e5) !important; color: white !important; border-radius: 16px 16px 4px 16px !important; border: none !important; font-size: 14px !important; line-height: 1.6 !important; }
#chatbot .bot .message { background: transparent !important; border: none !important; color: var(--text) !important; font-size: 14px !important; line-height: 1.6 !important; }
/* Gradio 5 prose / markdown inside bubbles */
#chatbot .bubble-wrap .bubble .prose { color: inherit !important; font-family: 'Inter', sans-serif !important; }
#chatbot .bubble-wrap.user .bubble .prose { color: white !important; }
#chatbot .bubble-wrap.bot .bubble .prose { color: var(--text) !important; }
/* Avatar */
#chatbot .bubble-wrap .avatar-container { width: 32px !important; height: 32px !important; }

/* ── Chat Input ─────────────────────────────────────────────────────────────── */
.chat-input-container { background: rgba(15,23,42,0.6) !important; border: 1px solid var(--border) !important; border-radius: 12px !important; padding: 6px !important; margin-top: 24px !important; align-items: center !important; }
.chat-input textarea, .chat-input input { background: transparent !important; border: none !important; color: white !important; font-size: 14px !important; box-shadow: none !important; padding: 12px !important; font-family: 'Inter', sans-serif !important; }
.chat-input textarea:focus, .chat-input input:focus { outline: none !important; box-shadow: none !important; border: none !important; }
.chat-input label { display: none !important; }
.send-btn { background: #4f46e5 !important; border: none !important; color: white !important; border-radius: 8px !important; width: 44px !important; height: 44px !important; min-width: 44px !important; padding: 0 !important; display: flex !important; justify-content: center !important; align-items: center !important; transition: background 0.2s !important; box-shadow: none !important; }
.send-btn:hover { background: #6366f1 !important; }

/* ── Right Panel ───────────────────────────────────────────────────────────── */
.right-col { background: transparent !important; padding: 0 !important; display: flex !important; flex-direction: column !important; gap: 16px !important; }
.robot-img { border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid var(--border); width: 100%; display: block; }
.robot-img button, .robot-img .icon-buttons, .robot-img .image-button-container { display: none !important; }
/* Gradio 5 image component */
.robot-img .upload-container, .robot-img .image-container { border: none !important; background: transparent !important; }
.thinking-card { background: rgba(15,23,42,0.8); border: 1px solid rgba(59,130,246,0.3); border-radius: 12px; padding: 12px 20px; display: flex; align-items: center; gap: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); font-size: 14px; font-weight: 500; color: #fff; }
.thinking-dots { display: flex; gap: 4px; margin-left: auto; }
.thinking-dots div { width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; animation: blink 1.4s infinite both; }
.thinking-dots div:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots div:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0% { opacity: 0.2; } 20% { opacity: 1; } 100% { opacity: 0.2; } }

/* ── Suggested Actions ─────────────────────────────────────────────────────── */
.suggested-actions { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 16px !important; padding: 24px !important; flex-grow: 1 !important; }
.action-btn { background: transparent !important; border: none !important; border-bottom: 1px solid rgba(255,255,255,0.05) !important; border-radius: 0 !important; padding: 16px 0 !important; display: flex !important; align-items: center !important; gap: 12px !important; text-align: left !important; color: white !important; font-size: 14px !important; justify-content: flex-start !important; box-shadow: none !important; width: 100% !important; cursor: pointer; transition: all 0.2s; }
.action-btn:last-child { border-bottom: none !important; }
.action-btn:hover { background: rgba(255,255,255,0.02) !important; padding-left: 8px !important; }
.action-icon { font-size: 20px; width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.05); flex-shrink: 0; }
.action-text { display: flex; flex-direction: column; flex-grow: 1; }
.action-subtext { font-size: 11px; color: var(--muted); }
.action-arrow { margin-left: auto; color: var(--muted); font-size: 18px; }

/* ── Hide Gradio chrome ────────────────────────────────────────────────────── */
footer { display: none !important; }
.hide { display: none !important; }
/* Gradio 5 loader */
#loading { background: var(--bg) !important; }
"""

# ── Dark Gradio 5 Theme ───────────────────────────────────────────────────────
dark_theme = gr.themes.Base(
    primary_hue="indigo",
    secondary_hue="blue",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "sans-serif"],
).set(
    body_background_fill="#090a0f",
    body_background_fill_dark="#090a0f",
    block_background_fill="#0c101a",
    block_background_fill_dark="#0c101a",
    block_border_color="#1e293b",
    block_border_color_dark="#1e293b",
    button_primary_background_fill="#4f46e5",
    button_primary_background_fill_hover="#6366f1",
    button_primary_text_color="white",
    input_background_fill="rgba(15,23,42,0.6)",
    input_background_fill_dark="rgba(15,23,42,0.6)",
    input_border_color="#1e293b",
    chatbot_text_size="sm",
    body_text_color="#f8fafc",
    body_text_color_dark="#f8fafc",
)

INITIAL_HISTORY = [
    {"role": "user", "content": "How do I reset my password?"},
    {"role": "assistant", "content": "You can reset your password via the **Self-Service Portal** at `portal.company.com`.\n\nEnsure your new password is **12+ characters** long. If you have any issues, feel free to ask!"},
]

def build_ui():
    with gr.Blocks(title="ARIA IT Support", theme=dark_theme, css=CSS) as demo:
        gr.HTML("""
        <div class="navbar">
            <div class="logo-circle">
                <div class="logo-inner">⚡</div>
            </div>
            <div>
                <div style="font-size: 22px; font-weight: 700; letter-spacing: -0.5px; color:#f8fafc;">ARIA</div>
                <div style="font-size: 11px; color: #94a3b8; letter-spacing: 0.5px;">IT Support Assistant · <span style="color:#3b82f6;">Groq Powered</span></div>
            </div>
            <div class="metrics-container">
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">Active Tickets</span>
                        <span class="metric-value">24 <span class="metric-value-up">▲ 12%</span></span>
                    </div>
                    <div class="metric-icon" style="color:#3b82f6;">🎫</div>
                </div>
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">Security Alerts</span>
                        <span class="metric-value">2 <span class="metric-value-up" style="color:#ef4444;">▲ 100%</span></span>
                    </div>
                    <div class="metric-icon" style="color:#ef4444;">🛡️</div>
                </div>
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">AI Status</span>
                        <span class="metric-value" style="color:#10b981;">Online</span>
                        <span style="font-size:10px; color:#94a3b8; margin-top:-4px;">Groq Connected</span>
                    </div>
                    <div class="metric-icon" style="color:#0ea5e9;">🌐</div>
                </div>
                <div class="metric-card">
                    <div class="metric-card-content">
                        <span class="metric-label">Retrieval Latency</span>
                        <span class="metric-value" style="color:#0ea5e9;">210ms</span>
                        <span style="font-size:10px; color:#10b981; margin-top:-4px;">Optimal</span>
                    </div>
                    <div class="metric-icon" style="color:#6366f1;">⏱️</div>
                </div>
            </div>
            <div class="online-badge">
                <div class="online-dot"></div> ARIA Online
            </div>
        </div>
        """)

        with gr.Row(equal_height=False):
            # ── Left Sidebar ────────────────────────────────────────────────────
            with gr.Column(scale=20, min_width=240, elem_classes="left-col"):
                gr.HTML("<div class='section-title'>QUICK ACTIONS</div>")
                btn1 = gr.Button("🔑 Password Reset", elem_classes="btn-active")
                btn2 = gr.Button("🌐 VPN Setup", elem_classes="btn-glass")
                btn3 = gr.Button("📁 Recover Files", elem_classes="btn-glass")
                btn4 = gr.Button("🔒 Setup MFA", elem_classes="btn-glass")

                gr.HTML("<div class='section-title'>IT CONTACTS</div>")
                gr.HTML("""
                <div class='it-contact'>
                    <div class='it-contact-icon'>✉️</div>
                    <div style='flex-grow:1;'>
                        <div style='font-weight:600;font-size:13px;color:white;display:flex;justify-content:space-between;align-items:center;'>Helpdesk <span style='width:6px;height:6px;background:#10b981;border-radius:50%;display:inline-block;'></span></div>
                        <div style='font-size:11px;color:#94a3b8;margin-top:2px;'>helpdesk@company.com<br>Ext. 1234 · Mon–Fri 8am–6pm</div>
                    </div>
                </div>
                <div class='it-contact'>
                    <div class='it-contact-icon'>📞</div>
                    <div style='flex-grow:1;'>
                        <div style='font-weight:600;font-size:13px;color:white;display:flex;justify-content:space-between;align-items:center;'>Emergency (24/7) <span style='width:6px;height:6px;background:#ef4444;border-radius:50%;display:inline-block;'></span></div>
                        <div style='font-size:11px;color:#94a3b8;margin-top:2px;'>Ext. 9911</div>
                    </div>
                </div>
                """)
                sys_status = gr.Button("📊 System Status ›", elem_classes="btn-glass")

            # ── Center Chat ─────────────────────────────────────────────────────
            with gr.Column(scale=50, min_width=480, elem_classes="center-col"):
                gr.HTML("<div style='color:#2563eb; font-weight:600; font-size:14px; margin-bottom:16px;'>ARIA</div>")
                chatbot = gr.Chatbot(
                    value=INITIAL_HISTORY,
                    elem_id="chatbot",
                    height=500,
                    show_label=False,
                    type="messages",
                    avatar_images=(None, "https://api.iconify.design/ri:robot-2-fill.svg?color=%233b82f6"),
                    show_copy_button=True,
                    bubble_full_width=False,
                )
                with gr.Row(elem_classes="chat-input-container"):
                    msg = gr.Textbox(
                        placeholder="Ask me anything about IT support...",
                        show_label=False,
                        scale=10,
                        elem_classes="chat-input",
                        container=False,
                        lines=1,
                    )
                    send = gr.Button("➤", scale=1, elem_classes="send-btn", min_width=44)

                gr.HTML("""
                <div style='text-align:center; padding-top:8px; font-size:10px; color:#475569;'>
                    ARIA may make mistakes. Verify important information with your IT team.
                </div>
                <div style='display:flex;justify-content:space-between;padding:16px 0 0 0;font-size:11px;color:#94a3b8; border-top:1px solid rgba(255,255,255,0.05); margin-top:16px;'>
                    <div style='display:flex; gap:16px;'>
                        <span><span style='color:#10b981;'>●</span> RAG: Active</span>
                        <span><span style='color:#10b981;'>●</span> Vector DB: Chroma</span>
                        <span><span style='color:#10b981;'>●</span> Model: llama-3.3-70b</span>
                    </div>
                    <div id="clear-trigger" style='cursor:pointer; display:flex; align-items:center; gap:4px;'>🗑️ Clear Chat</div>
                </div>
                """)
                clear = gr.Button("Clear", elem_id="clear-btn", visible=False)

            # ── Right Panel ─────────────────────────────────────────────────────
            with gr.Column(scale=28, min_width=280, elem_classes="right-col"):
                gr.Image(
                    "robot_custom.png",
                    show_label=False,
                    interactive=False,
                    container=False,
                    elem_classes="robot-img",
                    show_download_button=False,
                    show_fullscreen_button=False,
                )
                gr.HTML("""
                <div class="thinking-card">
                    <span>🧠</span>
                    <span>ARIA is analyzing...</span>
                    <div class="thinking-dots"><div></div><div></div><div></div></div>
                </div>
                """)

                with gr.Group(elem_classes="suggested-actions"):
                    gr.HTML("<div class='section-title'>SUGGESTED ACTIONS</div>")
                    gr.HTML("""
                    <button class='action-btn'>
                        <div class='action-icon' style='color:#3b82f6;'>🎫</div>
                        <div class='action-text'>Create Jira Ticket<span class='action-subtext'>IT-1487</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    <button class='action-btn'>
                        <div class='action-icon' style='color:#8b5cf6;'>🔔</div>
                        <div class='action-text'>Page Infrastructure Team<span class='action-subtext'>#infra-oncall</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    <button class='action-btn'>
                        <div class='action-icon' style='color:#eab308;'>✉️</div>
                        <div class='action-text'>Send Email to User<span class='action-subtext'>user@company.com</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    <button class='action-btn'>
                        <div class='action-icon' style='color:#ef4444;'>🛡️</div>
                        <div class='action-text'>Security Escalation<span class='action-subtext' style='color:#ef4444;'>High Priority</span></div>
                        <div class='action-arrow'>›</div>
                    </button>
                    """)

        # ── Event Handlers ────────────────────────────────────────────────────
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

        msg.submit(user_submit, [msg, chatbot], [msg, chatbot]).then(bot_respond, chatbot, chatbot)
        send.click(user_submit, [msg, chatbot], [msg, chatbot]).then(bot_respond, chatbot, chatbot)
        clear.click(lambda: [], None, chatbot)

        for btn, query in [
            (btn1, "How do I reset my password?"),
            (btn2, "Help me setup VPN"),
            (btn3, "How to recover deleted files?"),
            (btn4, "How to setup MFA?"),
            (sys_status, "What is the current system status and are there any active alerts?")
        ]:
            btn.click(
                lambda q=query: [{"role": "user", "content": q}],
                outputs=chatbot
            ).then(bot_respond, chatbot, chatbot)

    return demo

# ── Startup ───────────────────────────────────────────────────────────────────
print("Starting ARIA with Groq...")
ok, msg = initialize_system()
print(msg)

demo = build_ui()
demo.queue()

demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860)),
    allowed_paths=["."],
)
