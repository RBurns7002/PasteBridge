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
import string
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


# Helper function to generate short slug
def generate_slug(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# Define Models
class NotepadEntry(BaseModel):
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Notepad(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slug: str = Field(default_factory=lambda: generate_slug())
    entries: List[NotepadEntry] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NotepadCreate(BaseModel):
    pass  # Empty, we auto-generate everything

class AppendTextRequest(BaseModel):
    text: str

class NotepadResponse(BaseModel):
    id: str
    slug: str
    entries: List[NotepadEntry]
    created_at: datetime
    updated_at: datetime
    share_url: Optional[str] = None


# Notepad API Routes
@api_router.post("/notepad", response_model=NotepadResponse)
async def create_notepad():
    """Create a new notepad session"""
    notepad = Notepad()
    notepad_dict = notepad.dict()
    await db.notepads.insert_one(notepad_dict)
    return NotepadResponse(**notepad_dict)


@api_router.get("/notepad/{slug}", response_model=NotepadResponse)
async def get_notepad(slug: str):
    """Get notepad content by slug"""
    notepad = await db.notepads.find_one({"slug": slug})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    return NotepadResponse(**notepad)


@api_router.post("/notepad/{slug}/append", response_model=NotepadResponse)
async def append_to_notepad(slug: str, request: AppendTextRequest):
    """Append text to notepad"""
    notepad = await db.notepads.find_one({"slug": slug})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    
    new_entry = NotepadEntry(text=request.text)
    
    await db.notepads.update_one(
        {"slug": slug},
        {
            "$push": {"entries": new_entry.dict()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    # Return updated notepad
    updated_notepad = await db.notepads.find_one({"slug": slug})
    return NotepadResponse(**updated_notepad)


@api_router.delete("/notepad/{slug}")
async def clear_notepad(slug: str):
    """Clear all entries from notepad"""
    notepad = await db.notepads.find_one({"slug": slug})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    
    await db.notepads.update_one(
        {"slug": slug},
        {
            "$set": {"entries": [], "updated_at": datetime.utcnow()}
        }
    )
    return {"message": "Notepad cleared"}


# Web View Route - HTML page for viewing notepad
@api_router.get("/notepad/{slug}/view", response_class=HTMLResponse)
async def view_notepad(slug: str):
    """Web view of notepad - auto-refreshing HTML page"""
    notepad = await db.notepads.find_one({"slug": slug})
    if not notepad:
        return HTMLResponse(
            content="<html><body><h1>Notepad not found</h1></body></html>",
            status_code=404
        )
    
    entries_html = ""
    for entry in notepad.get("entries", []):
        timestamp = entry.get("timestamp", datetime.utcnow())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = timestamp.strftime("%H:%M:%S")
        text = entry.get("text", "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        entries_html += f'''
        <div class="entry">
            <div class="timestamp">{time_str}</div>
            <div class="text">{text}</div>
        </div>
        '''
    
    if not entries_html:
        entries_html = '<div class="empty">No entries yet. Copy text on your phone to see it appear here!</div>'
    
    html_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PasteBridge - {slug}</title>
        <meta http-equiv="refresh" content="3">
        <style>
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                min-height: 100vh;
                color: #e4e4e7;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                padding: 30px 0;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                margin-bottom: 30px;
            }}
            .header h1 {{
                font-size: 2rem;
                color: #60a5fa;
                margin-bottom: 10px;
            }}
            .header .slug {{
                font-family: monospace;
                background: rgba(96, 165, 250, 0.2);
                padding: 8px 16px;
                border-radius: 20px;
                display: inline-block;
                font-size: 0.9rem;
            }}
            .status {{
                text-align: center;
                font-size: 0.8rem;
                color: #a1a1aa;
                margin-bottom: 20px;
            }}
            .status .dot {{
                display: inline-block;
                width: 8px;
                height: 8px;
                background: #22c55e;
                border-radius: 50%;
                margin-right: 6px;
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
            }}
            .entries {{
                display: flex;
                flex-direction: column;
                gap: 16px;
            }}
            .entry {{
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 16px;
                border-left: 3px solid #60a5fa;
            }}
            .entry .timestamp {{
                font-size: 0.75rem;
                color: #a1a1aa;
                margin-bottom: 8px;
                font-family: monospace;
            }}
            .entry .text {{
                font-size: 1rem;
                line-height: 1.6;
                word-break: break-word;
                white-space: pre-wrap;
            }}
            .empty {{
                text-align: center;
                padding: 60px 20px;
                color: #71717a;
                font-size: 1.1rem;
            }}
            .footer {{
                text-align: center;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.1);
                color: #71717a;
                font-size: 0.8rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>PasteBridge</h1>
                <div class="slug">📋 {slug}</div>
            </div>
            <div class="status">
                <span class="dot"></span>Auto-refreshing every 3 seconds
            </div>
            <div class="entries">
                {entries_html}
            </div>
            <div class="footer">
                Clipboard to Web Notepad
            </div>
        </div>
    </body>
    </html>
    '''
    
    return HTMLResponse(content=html_content)


# Health check
@api_router.get("/")
async def root():
    return {"message": "PasteBridge API is running"}


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
