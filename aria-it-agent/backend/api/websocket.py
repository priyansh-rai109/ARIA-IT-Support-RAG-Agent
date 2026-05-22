import json
import urllib.parse
import asyncio
import requests
import traceback
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.services.rag_pipeline import retrieve_hybrid_context
from backend.services.memory import (
    save_message,
    get_history,
    get_user_preferences,
    extract_and_save_preferences,
    get_relevant_tickets
)

router = APIRouter()

def stream_groq_response(messages: list):
    """Synchronous generator to stream tokens from Groq API."""
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": GROQ_MODEL, "messages": messages, "stream": True},
        stream=True,
        timeout=10
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
                        yield delta
                except Exception:
                    pass

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Establishes real-time full-duplex streaming chat with ARIA."""
    await websocket.accept()
    print("WebSocket client successfully connected to ARIA backend.")
    
    try:
        while True:
            # 1. Receive incoming message payload
            data = await websocket.receive_text()
            payload = json.loads(data)
            message = payload.get("message", "").strip()
            user_id = payload.get("user_id", "default_user")
            
            if not message:
                continue
            
            # 2. Retrieve history (Short-term Context)
            history = get_history(user_id, limit=6)
            
            # 3. Retrieve grounding data (Hybrid RAG + SQLite Tickets + User Preferences)
            context_text, sources = retrieve_hybrid_context(message)
            related_tickets = get_relevant_tickets(message)
            user_prefs = get_user_preferences(user_id)
            
            # 4. Formulate robust Enterprise System Prompt
            system_instruction = (
                "You are ARIA, a highly skilled Enterprise IT Support and Autonomous Operations AI.\n"
                f"Current time: {datetime_now_str()}\n\n"
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
            for turn in history:
                api_messages.append({"role": turn["role"], "content": turn["content"]})
            api_messages.append({"role": "user", "content": message})
            
            # Save user prompt in DB
            save_message(user_id, "user", message)
            
            # 5. Stream response back to WebSocket client token-by-token
            answer = ""
            try:
                # Wrap the synchronous requests post in to_thread to keep the async loop non-blocking
                loop = asyncio.get_running_loop()
                generator = await loop.run_in_executor(None, lambda: list(stream_groq_response(api_messages)))
                
                for token in generator:
                    answer += token
                    await websocket.send_json({"type": "token", "content": token})
                    await asyncio.sleep(0.01) # Micro-sleep to ensure smooth UI animation rendering
                    
            except Exception as stream_err:
                traceback.print_exc()
                answer_err = f"API error occurred during streaming: {str(stream_err)}"
                await websocket.send_json({"type": "token", "content": answer_err})
                answer += answer_err
                
            # 6. Append clickable source cards HTML if sources are resolved
            cards_html = ""
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
                
                # Send the final sources HTML to the client
                await websocket.send_json({"type": "sources", "content": cards_html})
                
            # Save assistant response to DB
            save_message(user_id, "assistant", answer + ("\n\n" + cards_html if cards_html else ""))
            
            # 7. Asynchronously trigger user preference extraction in the background
            asyncio.create_task(async_extract_prefs(user_id, message, answer))
            
            # Send completion notification
            await websocket.send_json({"type": "end"})
            
    except WebSocketDisconnect:
        print("WebSocket client successfully disconnected.")
    except Exception as e:
        print(f"WebSocket execution encountered exception: {e}")
        traceback.print_exc()

def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")

async def async_extract_prefs(user_id, user_message, answer):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: extract_and_save_preferences(user_id, user_message, answer))
