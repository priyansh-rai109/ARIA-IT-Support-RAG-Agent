# ARIA — Autonomous Resolution & Intelligence Agent
### IT Support RAG Agentic AI · Powered by Claude + ChromaDB + Gradio

---

## Overview

ARIA is a production-ready IT Support AI assistant that uses Retrieval-Augmented Generation (RAG) to answer employee IT questions accurately from a curated knowledge base. It streams responses in real time via a polished Gradio web UI.

**Stack:**
| Layer | Technology |
|---|---|
| LLM | Anthropic Claude 3.5 Haiku |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| Vector Store | ChromaDB (in-memory) |
| Orchestration | LangChain |
| UI | Gradio 4 |

---

## Quick Start

### 1. Create & activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure your API key
Edit `.env` and paste your [Anthropic API key](https://console.anthropic.com):
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Run ARIA
```bash
python app.py
```

Open **http://localhost:7860** in your browser.

---

## Knowledge Base

ARIA ships with **10 built-in IT support articles**:

| # | Article | Category |
|---|---|---|
| 1 | Password Reset Procedure | Account Management |
| 2 | VPN Setup & Troubleshooting | Network & Connectivity |
| 3 | Software Installation Policy | Software & Licensing |
| 4 | Email / Outlook Configuration | Email & Communication |
| 5 | Laptop Hardware Troubleshooting | Hardware |
| 6 | MFA Setup & Troubleshooting | Security & Access |
| 7 | Printer Setup & Troubleshooting | Hardware |
| 8 | Microsoft Teams Troubleshooting | Email & Communication |
| 9 | IT Helpdesk Escalation & SLA | Support Processes |
| 10 | Data Backup & Recovery Policy | Data & Security |

---

## Project Structure

```
aria-it-agent/
├── app.py              # Full application (RAG pipeline + Gradio UI)
├── requirements.txt    # Python dependencies
├── .env                # API keys (never commit this)
├── .gitignore
└── README.md
```

---

## Architecture

```
User Question
     │
     ▼
[ Gradio UI ]
     │
     ▼
[ RAG Retriever ]  ──→  ChromaDB Vector Store
     │                  (HuggingFace Embeddings)
     ▼
[ Claude 3.5 Haiku ]  ←─  Streamed Response
     │
     ▼
[ Gradio UI ]  ──→  User (with source citations)
```

---

## Configuration

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | ✅ Yes |

---

## License

MIT License — free to use, modify, and distribute.
