from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
import random


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Word lists for memorable codes
ADJECTIVES = [
    'red', 'blue', 'green', 'gold', 'silver', 'bright', 'dark', 'swift',
    'calm', 'wild', 'cool', 'warm', 'soft', 'bold', 'quick', 'slow',
    'big', 'tiny', 'happy', 'lucky', 'sunny', 'rainy', 'snowy', 'windy',
    'fresh', 'crisp', 'smooth', 'sharp', 'sweet', 'spicy', 'salty', 'tangy'
]

NOUNS = [
    'tiger', 'eagle', 'wolf', 'bear', 'hawk', 'lion', 'fox', 'deer',
    'moon', 'star', 'sun', 'cloud', 'rain', 'snow', 'wind', 'storm',
    'tree', 'leaf', 'rose', 'lily', 'oak', 'pine', 'palm', 'fern',
    'rock', 'wave', 'fire', 'ice', 'sand', 'lake', 'river', 'peak'
]


def generate_memorable_code():
    """Generate a short, memorable code like 'red-tiger-42'"""
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num = random.randint(10, 99)
    return f"{adj}{noun}{num}"


# Define Models
class NotepadEntry(BaseModel):
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Notepad(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str = Field(default_factory=generate_memorable_code)
    entries: List[NotepadEntry] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NotepadCreate(BaseModel):
    pass

class AppendTextRequest(BaseModel):
    text: str

class NotepadResponse(BaseModel):
    id: str
    code: str
    entries: List[NotepadEntry]
    created_at: datetime
    updated_at: datetime

class CodeLookupRequest(BaseModel):
    code: str


# Notepad API Routes
@api_router.post("/notepad", response_model=NotepadResponse)
async def create_notepad():
    """Create a new notepad session with memorable code"""
    for _ in range(10):
        notepad = Notepad()
        existing = await db.notepads.find_one({"code": notepad.code})
        if not existing:
            break
        notepad = Notepad()
    
    notepad_dict = notepad.dict()
    await db.notepads.insert_one(notepad_dict)
    return NotepadResponse(**notepad_dict)


@api_router.get("/notepad/{code}", response_model=NotepadResponse)
async def get_notepad(code: str):
    """Get notepad content by code"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found. Check your code.")
    return NotepadResponse(**notepad)


@api_router.post("/notepad/lookup", response_model=NotepadResponse)
async def lookup_notepad(request: CodeLookupRequest):
    """Lookup notepad by code (for the landing page)"""
    code = request.code.lower().strip()
    notepad = await db.notepads.find_one({"code": code})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found. Check your code.")
    return NotepadResponse(**notepad)


@api_router.post("/notepad/{code}/append", response_model=NotepadResponse)
async def append_to_notepad(code: str, request: AppendTextRequest):
    """Append text to notepad"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    
    new_entry = NotepadEntry(text=request.text)
    
    await db.notepads.update_one(
        {"code": code.lower()},
        {
            "$push": {"entries": new_entry.dict()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    updated_notepad = await db.notepads.find_one({"code": code.lower()})
    return NotepadResponse(**updated_notepad)


@api_router.delete("/notepad/{code}")
async def clear_notepad(code: str):
    """Clear all entries from notepad"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    
    await db.notepads.update_one(
        {"code": code.lower()},
        {"$set": {"entries": [], "updated_at": datetime.utcnow()}}
    )
    return {"message": "Notepad cleared"}


# Landing Page - Enter code to view notepad
@api_router.get("/", response_class=HTMLResponse)
async def landing_page():
    """Landing page where users enter their code"""
    html_content = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PasteBridge - Clipboard to PC</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #e4e4e7;
                padding: 20px;
            }
            .container { max-width: 480px; width: 100%; text-align: center; }
            .logo { font-size: 3rem; margin-bottom: 8px; }
            h1 { font-size: 2.5rem; color: #60a5fa; margin-bottom: 8px; font-weight: 700; }
            .tagline { color: #a1a1aa; font-size: 1.1rem; margin-bottom: 48px; }
            .card {
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 40px 32px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.1);
            }
            .card h2 { font-size: 1.2rem; color: #d4d4d8; margin-bottom: 24px; font-weight: 500; }
            .code-input {
                width: 100%;
                padding: 16px 20px;
                font-size: 1.5rem;
                text-align: center;
                background: rgba(0,0,0,0.3);
                border: 2px solid rgba(96, 165, 250, 0.3);
                border-radius: 12px;
                color: #ffffff;
                font-family: 'SF Mono', Monaco, 'Courier New', monospace;
                letter-spacing: 2px;
                outline: none;
                transition: all 0.2s;
            }
            .code-input:focus { border-color: #60a5fa; box-shadow: 0 0 20px rgba(96, 165, 250, 0.2); }
            .code-input::placeholder { color: #52525b; letter-spacing: 1px; }
            .submit-btn {
                width: 100%;
                padding: 16px;
                font-size: 1.1rem;
                font-weight: 600;
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 12px;
                cursor: pointer;
                margin-top: 16px;
                transition: all 0.2s;
            }
            .submit-btn:hover { background: #2563eb; transform: translateY(-1px); }
            .error { color: #ef4444; margin-top: 16px; font-size: 0.95rem; display: none; }
            .error.show { display: block; }
            .example { margin-top: 24px; color: #71717a; font-size: 0.85rem; }
            .example code { background: rgba(96, 165, 250, 0.1); padding: 4px 8px; border-radius: 4px; color: #60a5fa; }
            .footer { margin-top: 32px; color: #52525b; font-size: 0.8rem; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">📋</div>
            <h1>PasteBridge</h1>
            <p class="tagline">Phone clipboard → PC notepad</p>
            <div class="card">
                <h2>Enter your notepad code</h2>
                <form id="codeForm" onsubmit="handleSubmit(event)">
                    <input type="text" id="codeInput" class="code-input" placeholder="redtiger42" autocomplete="off" autocapitalize="none" spellcheck="false" />
                    <button type="submit" class="submit-btn">View Notepad</button>
                </form>
                <p id="error" class="error"></p>
                <p class="example">Example: <code>suntiger42</code></p>
            </div>
            <p class="footer">Get the code from the PasteBridge app on your phone</p>
        </div>
        <script>
            async function handleSubmit(e) {
                e.preventDefault();
                const code = document.getElementById('codeInput').value.trim().toLowerCase();
                const errorEl = document.getElementById('error');
                if (!code) { errorEl.textContent = 'Please enter a code'; errorEl.classList.add('show'); return; }
                errorEl.classList.remove('show');
                try {
                    const response = await fetch('/api/notepad/lookup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
                    if (response.ok) { window.location.href = '/api/notepad/' + code + '/view'; }
                    else { const data = await response.json(); errorEl.textContent = data.detail || 'Notepad not found.'; errorEl.classList.add('show'); }
                } catch (err) { errorEl.textContent = 'Connection error. Please try again.'; errorEl.classList.add('show'); }
            }
            document.getElementById('codeInput').focus();
        </script>
    </body>
    </html>
    '''
    return HTMLResponse(content=html_content)


# Web View Route - HTML page for viewing notepad (NO auto-refresh, uses JS polling)
@api_router.get("/notepad/{code}/view", response_class=HTMLResponse)
async def view_notepad(code: str):
    """Web view of notepad - uses JavaScript polling to update without page refresh"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        return HTMLResponse(
            content="""<!DOCTYPE html><html><head><title>Not Found</title>
            <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0f0f1a;color:#fff;}
            .container{text-align:center;}h1{color:#ef4444;}a{color:#60a5fa;}</style></head>
            <body><div class="container"><h1>Notepad not found</h1><p>Check your code and try again.</p>
            <p><a href="/api/">← Back to home</a></p></div></body></html>""",
            status_code=404
        )
    
    html_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PasteBridge - {notepad.get("code")}</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
                min-height: 100vh;
                color: #e4e4e7;
                padding: 20px;
            }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 20px 0;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                margin-bottom: 24px;
            }}
            .header-left h1 {{ font-size: 1.5rem; color: #60a5fa; margin-bottom: 4px; }}
            .code-badge {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                font-family: 'SF Mono', Monaco, monospace;
                background: rgba(96, 165, 250, 0.15);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 1.1rem;
                color: #60a5fa;
                font-weight: 600;
            }}
            .status {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.85rem;
                color: #71717a;
                margin-bottom: 20px;
            }}
            .status .dot {{
                width: 8px;
                height: 8px;
                background: #22c55e;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
            .stats {{ text-align: right; }}
            .stats .count {{ font-size: 1.5rem; font-weight: 700; color: #ffffff; }}
            .stats .label {{ font-size: 0.8rem; color: #71717a; }}
            .entries {{ display: flex; flex-direction: column; gap: 12px; }}
            .entry {{
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 16px;
                border-left: 3px solid #60a5fa;
            }}
            .entry-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
            .timestamp {{ font-size: 0.75rem; color: #71717a; font-family: monospace; }}
            .copy-btn {{
                background: rgba(96, 165, 250, 0.2);
                border: none;
                color: #60a5fa;
                padding: 4px 12px;
                border-radius: 6px;
                font-size: 0.75rem;
                cursor: pointer;
            }}
            .copy-btn:hover {{ background: rgba(96, 165, 250, 0.3); }}
            .copy-btn.copied {{ background: #22c55e; color: white; }}
            .text {{ font-size: 1rem; line-height: 1.6; word-break: break-word; white-space: pre-wrap; color: #f4f4f5; }}
            .empty {{ text-align: center; padding: 80px 20px; color: #71717a; }}
            .empty-icon {{ font-size: 4rem; margin-bottom: 16px; opacity: 0.5; }}
            .empty p {{ font-size: 1.2rem; margin-bottom: 8px; }}
            .back-link {{ display: inline-block; margin-top: 24px; color: #60a5fa; text-decoration: none; font-size: 0.9rem; }}
            .back-link:hover {{ text-decoration: underline; }}
            .new-entry {{ animation: slideIn 0.3s ease-out; }}
            @keyframes slideIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <h1>PasteBridge</h1>
                    <div class="code-badge">🔗 {notepad.get("code")}</div>
                </div>
                <div class="stats">
                    <div class="count" id="entryCount">0</div>
                    <div class="label">entries</div>
                </div>
            </div>
            <div class="status">
                <span class="dot"></span>
                <span id="statusText">Live updating</span>
            </div>
            <div class="entries" id="entriesContainer">
                <div class="empty" id="emptyState">
                    <div class="empty-icon">📋</div>
                    <p>No entries yet</p>
                    <p style="font-size: 0.9rem; color: #52525b;">Copy text on your phone and tap the capture button</p>
                </div>
            </div>
            <a href="/api/" class="back-link">← Enter different code</a>
        </div>
        <script>
            const CODE = '{notepad.get("code")}';
            let lastEntryCount = 0;
            
            function escapeHtml(text) {{
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }}
            
            function formatTime(timestamp) {{
                const date = new Date(timestamp);
                return date.toLocaleTimeString('en-US', {{ hour12: false }});
            }}
            
            function copyText(btn, text) {{
                navigator.clipboard.writeText(text).then(() => {{
                    btn.textContent = 'Copied!';
                    btn.classList.add('copied');
                    setTimeout(() => {{
                        btn.textContent = 'Copy';
                        btn.classList.remove('copied');
                    }}, 2000);
                }});
            }}
            
            function renderEntries(entries) {{
                const container = document.getElementById('entriesContainer');
                const countEl = document.getElementById('entryCount');
                const emptyState = document.getElementById('emptyState');
                
                countEl.textContent = entries.length;
                
                if (entries.length === 0) {{
                    if (!emptyState) {{
                        container.innerHTML = `
                            <div class="empty" id="emptyState">
                                <div class="empty-icon">📋</div>
                                <p>No entries yet</p>
                                <p style="font-size: 0.9rem; color: #52525b;">Copy text on your phone and tap the capture button</p>
                            </div>
                        `;
                    }}
                    return;
                }}
                
                // Only update if there are new entries
                if (entries.length !== lastEntryCount) {{
                    const reversedEntries = [...entries].reverse();
                    container.innerHTML = reversedEntries.map((entry, index) => {{
                        const isNew = index === 0 && entries.length > lastEntryCount;
                        return `
                            <div class="entry ${{isNew ? 'new-entry' : ''}}">
                                <div class="entry-header">
                                    <span class="timestamp">${{formatTime(entry.timestamp)}}</span>
                                    <button class="copy-btn" onclick="copyText(this, ${{JSON.stringify(entry.text)}})">Copy</button>
                                </div>
                                <div class="text">${{escapeHtml(entry.text).replace(/\n/g, '<br>')}}</div>
                            </div>
                        `;
                    }}).join('');
                    lastEntryCount = entries.length;
                }}
            }}
            
            async function fetchEntries() {{
                try {{
                    const response = await fetch('/api/notepad/' + CODE);
                    if (response.ok) {{
                        const data = await response.json();
                        renderEntries(data.entries);
                        document.getElementById('statusText').textContent = 'Live updating';
                    }}
                }} catch (err) {{
                    document.getElementById('statusText').textContent = 'Connection lost, retrying...';
                }}
            }}
            
            // Initial fetch
            fetchEntries();
            
            // Poll every 3 seconds without refreshing the page
            setInterval(fetchEntries, 3000);
        </script>
    </body>
    </html>
    '''
    
    return HTMLResponse(content=html_content)


# Health check
@api_router.get("/health")
async def health():
    return {"status": "healthy", "service": "PasteBridge API"}


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
