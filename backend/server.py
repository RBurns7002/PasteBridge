from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import httpx
import time
from collections import defaultdict
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import random
import json
import io
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest


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

# Security
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Settings
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# Constants
GUEST_EXPIRATION_DAYS = 90
USER_EXPIRATION_DAYS = 365  # 1 year for registered users
PREMIUM_EXPIRATION_DAYS = None  # Never expires
EXPIRATION_WARNING_DAYS = 7


# ==================== Rate Limiting ====================

class RateLimiter:
    """Simple in-memory rate limiter"""
    def __init__(self):
        self.requests = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < window_seconds]
        if len(self.requests[key]) >= max_requests:
            return True
        self.requests[key].append(now)
        return False

rate_limiter = RateLimiter()

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class GoogleSessionRequest(BaseModel):
    session_id: str


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
    """Generate a short, memorable code like 'redtiger42'"""
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    num = random.randint(10, 99)
    return f"{adj}{noun}{num}"


def get_expiration_date(account_type: str = "guest"):
    """Get expiration date based on account type"""
    if account_type == "premium":
        return None  # Never expires
    elif account_type == "user":
        return datetime.utcnow() + timedelta(days=USER_EXPIRATION_DAYS)
    else:  # guest
        return datetime.utcnow() + timedelta(days=GUEST_EXPIRATION_DAYS)


def calculate_days_remaining(expires_at: datetime) -> int:
    """Calculate days remaining until expiration"""
    if not expires_at:
        return None  # Premium - never expires
    delta = expires_at - datetime.utcnow()
    return max(0, delta.days)


def is_expired(expires_at: datetime) -> bool:
    """Check if notepad is expired"""
    if not expires_at:
        return False
    return datetime.utcnow() > expires_at


# Password helpers
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# JWT helpers
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token (optional - returns None if not authenticated)"""
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    user = await db.users.find_one({"id": user_id})
    return user


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Require authentication - raises 401 if not authenticated"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ==================== Models ====================

class NotepadEntry(BaseModel):
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Notepad(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str = Field(default_factory=generate_memorable_code)
    entries: List[NotepadEntry] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    account_type: str = "guest"
    expires_at: Optional[datetime] = Field(default_factory=lambda: get_expiration_date("guest"))
    user_id: Optional[str] = None  # Link to user account


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    name: str = ""
    account_type: str = "user"  # user | premium
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    account_type: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    token: str
    message: str


class AppendTextRequest(BaseModel):
    text: str


class NotepadResponse(BaseModel):
    id: str
    code: str
    entries: List[NotepadEntry]
    created_at: datetime
    updated_at: datetime
    account_type: str = "guest"
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    is_expiring_soon: bool = False
    user_id: Optional[str] = None


class CodeLookupRequest(BaseModel):
    code: str


class LinkNotepadRequest(BaseModel):
    code: str


class BulkLinkRequest(BaseModel):
    codes: List[str]


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    name: str


class PushTokenRequest(BaseModel):
    token: str


class WebhookRequest(BaseModel):
    url: str
    events: List[str] = ["new_entry"]
    secret: Optional[str] = None


class SummarizeRequest(BaseModel):
    max_length: Optional[int] = 500


class FeedbackRequest(BaseModel):
    category: str  # "bug", "feature_request", "missing_feature", "other"
    title: str
    description: str
    severity: Optional[str] = "medium"  # "low", "medium", "high", "critical"


class SubscriptionCheckoutRequest(BaseModel):
    plan: str  # "pro", "business"
    origin_url: str


# Subscription plans defined server-side (never accept amounts from frontend)
SUBSCRIPTION_PLANS = {
    "pro": {"name": "Pro", "amount": 4.99, "currency": "usd", "expiration_days": 365, "max_notepads": None},
    "business": {"name": "Business", "amount": 14.99, "currency": "usd", "expiration_days": None, "max_notepads": None},
}


# ==================== Push Notification Helper ====================

async def send_push_notification(push_token: str, title: str, body: str, data: dict = None):
    """Send push notification via Expo's push service"""
    message = {
        "to": push_token,
        "sound": "default",
        "title": title,
        "body": body,
    }
    if data:
        message["data"] = data
    try:
        async with httpx.AsyncClient() as client_http:
            await client_http.post(
                "https://exp.host/--/api/v2/push/send",
                json=message,
                headers={"Content-Type": "application/json"}
            )
    except Exception as e:
        logging.getLogger(__name__).warning(f"Push notification failed: {e}")


# ==================== Background Cron Job ====================

async def cleanup_cron():
    """Background task that cleans up expired notepads every 6 hours"""
    log = logging.getLogger("cron")
    while True:
        try:
            await asyncio.sleep(6 * 60 * 60)  # 6 hours
            now = datetime.utcnow()
            result = await db.notepads.delete_many({
                "expires_at": {"$lt": now},
                "account_type": {"$in": ["guest", "user"]}
            })
            if result.deleted_count > 0:
                log.info(f"Cron: cleaned up {result.deleted_count} expired notepads")
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"Cron error: {e}")
            await asyncio.sleep(60)


def build_notepad_response(notepad: dict) -> NotepadResponse:
    """Build NotepadResponse with expiration info"""
    expires_at = notepad.get("expires_at")
    account_type = notepad.get("account_type", "guest")
    
    # Handle legacy notepads without expires_at
    if expires_at is None and account_type != "premium":
        created_at = notepad.get("created_at", datetime.utcnow())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        if account_type == "user":
            expires_at = created_at + timedelta(days=USER_EXPIRATION_DAYS)
        else:
            expires_at = created_at + timedelta(days=GUEST_EXPIRATION_DAYS)
    
    days_remaining = calculate_days_remaining(expires_at) if expires_at else None
    is_expiring_soon = days_remaining is not None and days_remaining <= EXPIRATION_WARNING_DAYS
    
    return NotepadResponse(
        id=notepad.get("id", str(notepad.get("_id", ""))),
        code=notepad.get("code"),
        entries=[NotepadEntry(**e) for e in notepad.get("entries", [])],
        created_at=notepad.get("created_at"),
        updated_at=notepad.get("updated_at"),
        account_type=account_type,
        expires_at=expires_at,
        days_remaining=days_remaining,
        is_expiring_soon=is_expiring_soon,
        user_id=notepad.get("user_id")
    )


# ==================== Auth Routes ====================

@api_router.post("/auth/register", response_model=AuthResponse)
async def register(data: UserRegister, request: Request):
    """Register a new user account"""
    ip = get_client_ip(request)
    if rate_limiter.is_rate_limited(f"register:{ip}", max_requests=5, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many registration attempts. Try again in 5 minutes.")

    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate password
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    # Create user
    user = User(
        email=data.email.lower(),
        password_hash=get_password_hash(data.password),
        name=data.name or data.email.split("@")[0]
    )
    
    await db.users.insert_one(user.dict())
    
    # Create token
    token = create_access_token({"sub": user.id})
    
    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            account_type=user.account_type,
            created_at=user.created_at
        ),
        token=token,
        message="Account created successfully"
    )


@api_router.post("/auth/login", response_model=AuthResponse)
async def login(data: UserLogin, request: Request):
    """Login with email and password"""
    ip = get_client_ip(request)
    if rate_limiter.is_rate_limited(f"login:{ip}", max_requests=10, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 5 minutes.")

    user = await db.users.find_one({"email": data.email.lower()})
    
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Create token
    token = create_access_token({"sub": user["id"]})
    
    return AuthResponse(
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user.get("name", ""),
            account_type=user.get("account_type", "user"),
            created_at=user["created_at"]
        ),
        token=token,
        message="Login successful"
    )


@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(require_auth)):
    """Get current user profile"""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user.get("name", ""),
        account_type=user.get("account_type", "user"),
        created_at=user["created_at"]
    )


@api_router.put("/auth/profile", response_model=UserResponse)
async def update_profile(data: ProfileUpdateRequest, user: dict = Depends(require_auth)):
    """Update user profile"""
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"name": data.name, "updated_at": datetime.utcnow()}}
    )
    
    updated_user = await db.users.find_one({"id": user["id"]})
    return UserResponse(
        id=updated_user["id"],
        email=updated_user["email"],
        name=updated_user.get("name", ""),
        account_type=updated_user.get("account_type", "user"),
        created_at=updated_user["created_at"]
    )


@api_router.post("/auth/change-password")
async def change_password(data: PasswordChangeRequest, user: dict = Depends(require_auth)):
    """Change user password"""
    if not verify_password(data.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": get_password_hash(data.new_password), "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Password changed successfully"}


@api_router.get("/auth/notepads", response_model=List[NotepadResponse])
async def get_user_notepads(user: dict = Depends(require_auth)):
    """Get all notepads owned by current user"""
    notepads = await db.notepads.find({"user_id": user["id"]}).to_list(100)
    return [build_notepad_response(n) for n in notepads]


@api_router.post("/auth/link-notepad", response_model=NotepadResponse)
async def link_notepad(data: LinkNotepadRequest, user: dict = Depends(require_auth)):
    """Link an existing guest notepad to user account"""
    notepad = await db.notepads.find_one({"code": data.code.lower()})
    
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    
    if notepad.get("user_id"):
        if notepad["user_id"] == user["id"]:
            raise HTTPException(status_code=400, detail="Notepad already linked to your account")
        raise HTTPException(status_code=400, detail="Notepad belongs to another user")
    
    # Link notepad to user and extend expiration
    new_expires = get_expiration_date(user.get("account_type", "user"))
    
    await db.notepads.update_one(
        {"code": data.code.lower()},
        {
            "$set": {
                "user_id": user["id"],
                "account_type": user.get("account_type", "user"),
                "expires_at": new_expires,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    updated = await db.notepads.find_one({"code": data.code.lower()})
    return build_notepad_response(updated)


@api_router.post("/auth/link-notepads")
async def bulk_link_notepads(data: BulkLinkRequest, user: dict = Depends(require_auth)):
    """Bulk link guest notepads to user account"""
    linked = []
    skipped = []
    new_expires = get_expiration_date(user.get("account_type", "user"))

    for code in data.codes:
        code_lower = code.lower().strip()
        notepad = await db.notepads.find_one({"code": code_lower})
        if not notepad:
            skipped.append({"code": code_lower, "reason": "not found"})
            continue
        if notepad.get("user_id"):
            if notepad["user_id"] == user["id"]:
                skipped.append({"code": code_lower, "reason": "already yours"})
            else:
                skipped.append({"code": code_lower, "reason": "belongs to another user"})
            continue
        await db.notepads.update_one(
            {"code": code_lower},
            {"$set": {
                "user_id": user["id"],
                "account_type": user.get("account_type", "user"),
                "expires_at": new_expires,
                "updated_at": datetime.utcnow()
            }}
        )
        linked.append(code_lower)

    return {
        "linked_count": len(linked),
        "skipped_count": len(skipped),
        "linked": linked,
        "skipped": skipped
    }


@api_router.post("/auth/push-token")
async def register_push_token(data: PushTokenRequest, user: dict = Depends(require_auth)):
    """Register a device push token for notifications"""
    await db.users.update_one(
        {"id": user["id"]},
        {"$addToSet": {"push_tokens": data.token}}
    )
    return {"message": "Push token registered"}


@api_router.delete("/auth/push-token")
async def remove_push_token(data: PushTokenRequest, user: dict = Depends(require_auth)):
    """Remove a device push token"""
    await db.users.update_one(
        {"id": user["id"]},
        {"$pull": {"push_tokens": data.token}}
    )
    return {"message": "Push token removed"}


# ==================== Webhook Routes ====================

@api_router.post("/auth/webhooks")
async def create_webhook(data: WebhookRequest, user: dict = Depends(require_auth)):
    """Register a webhook for notepad events"""
    webhook_id = str(uuid.uuid4())
    webhook_secret = data.secret or secrets.token_hex(16)
    webhook = {
        "id": webhook_id,
        "user_id": user["id"],
        "url": data.url,
        "events": data.events,
        "secret": webhook_secret,
        "active": True,
        "created_at": datetime.utcnow()
    }
    await db.webhooks.insert_one(webhook)
    return {
        "id": webhook_id,
        "url": data.url,
        "events": data.events,
        "secret": webhook_secret,
        "active": True
    }


@api_router.get("/auth/webhooks")
async def list_webhooks(user: dict = Depends(require_auth)):
    """List user's webhooks"""
    webhooks = await db.webhooks.find(
        {"user_id": user["id"]},
        {"_id": 0, "id": 1, "url": 1, "events": 1, "active": 1, "created_at": 1}
    ).to_list(50)
    return webhooks


@api_router.delete("/auth/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, user: dict = Depends(require_auth)):
    """Delete a webhook"""
    result = await db.webhooks.delete_one({"id": webhook_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"message": "Webhook deleted"}


async def fire_webhooks(user_id: str, event: str, payload: dict):
    """Fire webhooks for a user event"""
    webhooks = await db.webhooks.find(
        {"user_id": user_id, "active": True, "events": event}
    ).to_list(20)
    for wh in webhooks:
        try:
            async with httpx.AsyncClient(timeout=10) as client_http:
                await client_http.post(
                    wh["url"],
                    json={"event": event, "webhook_id": wh["id"], "data": payload},
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Secret": wh.get("secret", "")
                    }
                )
        except Exception:
            pass


# ==================== Notepad Routes ====================

@api_router.post("/notepad", response_model=NotepadResponse)
async def create_notepad(user: dict = Depends(get_current_user)):
    """Create a new notepad session"""
    for _ in range(10):
        notepad = Notepad()
        existing = await db.notepads.find_one({"code": notepad.code})
        if not existing:
            break
        notepad = Notepad()
    
    # If user is logged in, link notepad to their account
    if user:
        notepad.user_id = user["id"]
        notepad.account_type = user.get("account_type", "user")
        notepad.expires_at = get_expiration_date(notepad.account_type)
    
    notepad_dict = notepad.dict()
    await db.notepads.insert_one(notepad_dict)
    return build_notepad_response(notepad_dict)


@api_router.get("/notepad/{code}", response_model=NotepadResponse)
async def get_notepad(code: str):
    """Get notepad content by code"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found. Check your code.")
    
    # Check if expired
    expires_at = notepad.get("expires_at")
    if expires_at and is_expired(expires_at):
        raise HTTPException(status_code=410, detail="This notepad has expired and is no longer available.")
    
    return build_notepad_response(notepad)


@api_router.post("/notepad/lookup", response_model=NotepadResponse)
async def lookup_notepad(request: CodeLookupRequest):
    """Lookup notepad by code (for the landing page)"""
    code = request.code.lower().strip()
    notepad = await db.notepads.find_one({"code": code})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found. Check your code.")
    
    # Check if expired
    expires_at = notepad.get("expires_at")
    if expires_at and is_expired(expires_at):
        raise HTTPException(status_code=410, detail="This notepad has expired and is no longer available.")
    
    return build_notepad_response(notepad)


@api_router.post("/notepad/{code}/append", response_model=NotepadResponse)
async def append_to_notepad(code: str, request: AppendTextRequest):
    """Append text to notepad"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")
    
    # Check if expired
    expires_at = notepad.get("expires_at")
    if expires_at and is_expired(expires_at):
        raise HTTPException(status_code=410, detail="This notepad has expired. Please create a new one.")
    
    new_entry = NotepadEntry(text=request.text)
    
    await db.notepads.update_one(
        {"code": code.lower()},
        {
            "$push": {"entries": new_entry.dict()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    updated_notepad = await db.notepads.find_one({"code": code.lower()})

    # Fire webhooks if notepad has an owner
    owner_id = updated_notepad.get("user_id")
    if owner_id:
        asyncio.create_task(fire_webhooks(owner_id, "new_entry", {
            "code": code.lower(),
            "text": request.text,
            "entry_count": len(updated_notepad.get("entries", []))
        }))

    return build_notepad_response(updated_notepad)


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


# ==================== Export & AI Routes ====================

@api_router.get("/notepad/{code}/export")
async def export_notepad(code: str, format: str = "txt"):
    """Export notepad as txt, md, or json"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")

    entries = notepad.get("entries", [])
    notepad_code = notepad.get("code")

    if format == "json":
        export_data = {
            "code": notepad_code,
            "created_at": str(notepad.get("created_at")),
            "entries": [{"text": e["text"], "timestamp": str(e["timestamp"])} for e in entries]
        }
        content = json.dumps(export_data, indent=2)
        media_type = "application/json"
        filename = f"{notepad_code}.json"
    elif format == "md":
        lines = [f"# PasteBridge: {notepad_code}\n"]
        for e in entries:
            ts = e.get("timestamp", "")
            if isinstance(ts, datetime):
                ts = ts.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"### {ts}\n{e['text']}\n")
        content = "\n".join(lines)
        media_type = "text/markdown"
        filename = f"{notepad_code}.md"
    else:
        lines = [f"PasteBridge: {notepad_code}\n{'='*40}\n"]
        for e in entries:
            ts = e.get("timestamp", "")
            if isinstance(ts, datetime):
                ts = ts.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{ts}]\n{e['text']}\n{'-'*40}\n")
        content = "\n".join(lines)
        media_type = "text/plain"
        filename = f"{notepad_code}.txt"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@api_router.post("/notepad/{code}/summarize")
async def summarize_notepad(code: str, request: SummarizeRequest = None):
    """AI-summarize notepad content using GPT-5.2"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        raise HTTPException(status_code=404, detail="Notepad not found")

    entries = notepad.get("entries", [])
    if not entries:
        raise HTTPException(status_code=400, detail="Notepad has no entries to summarize")

    all_text = "\n\n".join([e["text"] for e in entries])
    max_len = request.max_length if request else 500

    try:
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"summarize-{code}-{uuid.uuid4().hex[:8]}",
            system_message=f"Summarize the following notepad content concisely in {max_len} characters or less. Focus on key topics and actionable items. Return only the summary, no preamble."
        ).with_model("openai", "gpt-5.2")

        summary = await chat.send_message(UserMessage(text=all_text))
        return {
            "code": code.lower(),
            "summary": summary,
            "entry_count": len(entries),
            "model": "gpt-5.2"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI summarization failed: {str(e)}")


# ==================== Admin Routes ====================

# --- Feedback Routes ---

@api_router.post("/feedback")
async def submit_feedback(data: FeedbackRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Submit bug report or feature request (works for guests and authenticated users)"""
    user_id = None
    user_email = None
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            user_obj = await db.users.find_one({"id": user_id})
            if user_obj:
                user_email = user_obj.get("email")
        except JWTError:
            pass

    feedback = {
        "id": str(uuid.uuid4()),
        "category": data.category,
        "title": data.title,
        "description": data.description,
        "severity": data.severity,
        "user_id": user_id,
        "user_email": user_email,
        "status": "open",
        "created_at": datetime.utcnow()
    }
    await db.feedback.insert_one(feedback)
    return {"id": feedback["id"], "message": "Feedback submitted. Thank you!"}


@api_router.get("/admin/feedback")
async def list_feedback(status: Optional[str] = None, category: Optional[str] = None):
    """List all feedback entries"""
    query = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    items = await db.feedback.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@api_router.post("/admin/feedback/summarize")
async def summarize_feedback():
    """AI-summarize all open feedback for quick inspection"""
    items = await db.feedback.find({"status": "open"}, {"_id": 0}).to_list(200)
    if not items:
        return {"summary": "No open feedback to summarize.", "count": 0}

    text_block = "\n\n".join([
        f"[{f['category'].upper()}] ({f['severity']}) {f['title']}: {f['description']}"
        for f in items
    ])

    try:
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"feedback-summary-{uuid.uuid4().hex[:8]}",
            system_message="You are a product manager reviewing user feedback. Categorize and summarize the feedback into: 1) Critical bugs to fix immediately, 2) Feature requests by popularity, 3) Missing features that may need README/docs updates, 4) Low priority items. Be concise and actionable."
        ).with_model("openai", "gpt-5.2")

        summary = await chat.send_message(UserMessage(text=text_block))
        return {"summary": summary, "count": len(items), "model": "gpt-5.2"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI summarization failed: {str(e)}")


@api_router.patch("/admin/feedback/{feedback_id}")
async def update_feedback_status(feedback_id: str, status: str):
    """Update feedback status (open, in_progress, resolved, wont_fix)"""
    result = await db.feedback.update_one(
        {"id": feedback_id},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"message": f"Feedback status updated to {status}"}


# --- Subscription Routes ---

@api_router.get("/subscription/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return {
        "free": {"name": "Free", "price": 0, "features": ["5 notepads", "90-day storage", "Basic clipboard sync"]},
        "pro": {"name": "Pro", "price": 4.99, "features": ["Unlimited notepads", "1-year storage", "AI summarization", "Export (txt/md/json)"]},
        "business": {"name": "Business", "price": 14.99, "features": ["Unlimited notepads", "Never-expire storage", "AI summarization", "Webhooks & automation", "Priority support"]},
    }


@api_router.post("/subscription/checkout")
async def create_subscription_checkout(data: SubscriptionCheckoutRequest, request_obj: "Request" = None, user: dict = Depends(require_auth)):
    """Create Stripe checkout session for subscription"""
    from starlette.requests import Request
    plan = SUBSCRIPTION_PLANS.get(data.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'pro' or 'business'")

    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(status_code=500, detail="Payment service not configured")

    origin = data.origin_url.rstrip("/")
    success_url = f"{origin}/api/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/api/subscription/plans-page"

    webhook_url = f"{origin}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    checkout_request = CheckoutSessionRequest(
        amount=plan["amount"],
        currency=plan["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user["id"],
            "plan": data.plan,
            "user_email": user.get("email", "")
        }
    )

    session = await stripe_checkout.create_checkout_session(checkout_request)

    # Store payment transaction
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "user_id": user["id"],
        "plan": data.plan,
        "amount": plan["amount"],
        "currency": plan["currency"],
        "payment_status": "pending",
        "created_at": datetime.utcnow()
    })

    return {"url": session.url, "session_id": session.session_id}


@api_router.get("/subscription/status/{session_id}")
async def get_subscription_status(session_id: str):
    """Check subscription payment status and activate if paid"""
    stripe_key = os.environ.get("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url="")

    status = await stripe_checkout.get_checkout_status(session_id)

    # Update transaction
    txn = await db.payment_transactions.find_one({"session_id": session_id})
    if txn:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": status.payment_status,
                "status": status.status,
                "updated_at": datetime.utcnow()
            }}
        )

        # Activate subscription if paid and not already activated
        if status.payment_status == "paid" and not txn.get("activated"):
            plan_name = txn.get("plan", "pro")
            plan = SUBSCRIPTION_PLANS.get(plan_name, SUBSCRIPTION_PLANS["pro"])
            exp_days = plan.get("expiration_days")

            await db.users.update_one(
                {"id": txn["user_id"]},
                {"$set": {
                    "account_type": plan_name,
                    "subscription_plan": plan_name,
                    "subscription_activated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}
            )

            # Upgrade all user's notepads
            update_fields = {"account_type": plan_name, "updated_at": datetime.utcnow()}
            if exp_days:
                update_fields["expires_at"] = datetime.utcnow() + timedelta(days=exp_days)
            else:
                update_fields["expires_at"] = None  # Never expires for business
            await db.notepads.update_many(
                {"user_id": txn["user_id"]},
                {"$set": update_fields}
            )

            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"activated": True}}
            )

    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency
    }


@api_router.get("/subscription/success", response_class=HTMLResponse)
async def subscription_success_page(session_id: str = ""):
    """Success page after subscription payment"""
    html = f'''<!DOCTYPE html><html><head><title>PasteBridge - Payment</title>
    <style>
    body {{ font-family: -apple-system, sans-serif; background: linear-gradient(135deg, #0f0f1a, #1a1a2e); min-height: 100vh; display: flex; align-items: center; justify-content: center; color: #e4e4e7; }}
    .card {{ background: rgba(255,255,255,0.05); border-radius: 20px; padding: 48px; max-width: 480px; text-align: center; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }}
    h1 {{ color: #60a5fa; margin-bottom: 16px; }}
    .status {{ padding: 12px 24px; border-radius: 8px; margin: 20px 0; font-weight: 600; }}
    .success {{ background: rgba(34,197,94,0.15); color: #22c55e; }}
    .pending {{ background: rgba(245,158,11,0.15); color: #fbbf24; }}
    .error {{ background: rgba(239,68,68,0.15); color: #ef4444; }}
    a {{ color: #60a5fa; text-decoration: none; }}
    </style></head><body><div class="card">
    <h1>PasteBridge</h1>
    <div id="status" class="status pending">Checking payment status...</div>
    <p id="message" style="color:#a1a1aa;margin-top:16px;"></p>
    <p style="margin-top:24px;"><a href="/api/">← Back to PasteBridge</a></p>
    </div>
    <script>
    async function pollStatus(sid, attempts) {{
        if (attempts >= 8) {{ document.getElementById('status').textContent = 'Timed out. Check your account.'; return; }}
        try {{
            var r = await fetch('/api/subscription/status/' + sid);
            var d = await r.json();
            if (d.payment_status === 'paid') {{
                document.getElementById('status').className = 'status success';
                document.getElementById('status').textContent = 'Payment Successful!';
                document.getElementById('message').textContent = 'Your subscription is now active. Open the PasteBridge app to enjoy your new features.';
                return;
            }} else if (d.status === 'expired') {{
                document.getElementById('status').className = 'status error';
                document.getElementById('status').textContent = 'Session expired';
                return;
            }}
            setTimeout(function() {{ pollStatus(sid, attempts + 1); }}, 2000);
        }} catch(e) {{
            document.getElementById('status').className = 'status error';
            document.getElementById('status').textContent = 'Error checking status';
        }}
    }}
    var sid = new URLSearchParams(window.location.search).get('session_id');
    if (sid) {{ pollStatus(sid, 0); }}
    else {{ document.getElementById('status').textContent = 'No session found'; }}
    </script></body></html>'''
    return HTMLResponse(content=html)


@api_router.get("/subscription/plans-page", response_class=HTMLResponse)
async def plans_page():
    """Web page showing subscription plans"""
    html = '''<!DOCTYPE html><html><head><title>PasteBridge - Plans</title>
    <style>
    body { font-family: -apple-system, sans-serif; background: linear-gradient(135deg, #0f0f1a, #1a1a2e); min-height: 100vh; color: #e4e4e7; padding: 40px 20px; }
    .container { max-width: 900px; margin: 0 auto; text-align: center; }
    h1 { color: #60a5fa; font-size: 2rem; margin-bottom: 8px; }
    .subtitle { color: #a1a1aa; margin-bottom: 40px; }
    .plans { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; }
    .plan { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 32px; flex: 1; min-width: 250px; max-width: 280px; border: 1px solid rgba(255,255,255,0.1); }
    .plan.featured { border-color: #60a5fa; box-shadow: 0 0 30px rgba(96,165,250,0.15); }
    .plan-name { font-size: 1.3rem; font-weight: 700; margin-bottom: 8px; }
    .plan-price { font-size: 2rem; font-weight: 700; color: #60a5fa; margin-bottom: 16px; }
    .plan-price span { font-size: 0.9rem; color: #71717a; font-weight: 400; }
    .features { list-style: none; text-align: left; margin-bottom: 24px; }
    .features li { padding: 6px 0; color: #a1a1aa; font-size: 0.9rem; }
    .features li::before { content: "✓ "; color: #22c55e; font-weight: 700; }
    a.btn { display: block; padding: 12px; background: #3b82f6; color: white; border-radius: 10px; text-decoration: none; font-weight: 600; }
    a.btn:hover { background: #2563eb; }
    .back { margin-top: 32px; }
    .back a { color: #60a5fa; text-decoration: none; }
    </style></head><body><div class="container">
    <h1>PasteBridge Plans</h1>
    <p class="subtitle">Upgrade for more power</p>
    <div class="plans">
    <div class="plan"><div class="plan-name">Free</div><div class="plan-price">$0<span>/forever</span></div>
    <ul class="features"><li>5 notepads</li><li>90-day storage</li><li>Clipboard sync</li></ul>
    <div style="color:#71717a;text-align:center;">Current Plan</div></div>
    <div class="plan featured"><div class="plan-name">Pro</div><div class="plan-price">$4.99<span>/month</span></div>
    <ul class="features"><li>Unlimited notepads</li><li>1-year storage</li><li>AI summarization</li><li>Export (txt/md/json)</li></ul>
    <div style="text-align:center;color:#a1a1aa;font-size:0.85rem;">Upgrade from the app</div></div>
    <div class="plan"><div class="plan-name">Business</div><div class="plan-price">$14.99<span>/month</span></div>
    <ul class="features"><li>Unlimited notepads</li><li>Never-expire storage</li><li>AI summarization</li><li>Webhooks & automation</li><li>Priority support</li></ul>
    <div style="text-align:center;color:#a1a1aa;font-size:0.85rem;">Upgrade from the app</div></div>
    </div>
    <div class="back"><a href="/api/">← Back to PasteBridge</a></div>
    </div></body></html>'''
    return HTMLResponse(content=html)


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: "Request"):
    """Handle Stripe webhook events"""
    from starlette.requests import Request
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")

    stripe_key = os.environ.get("STRIPE_API_KEY")
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url="")

    try:
        event = await stripe_checkout.handle_webhook(body, sig)
        if event.payment_status == "paid":
            txn = await db.payment_transactions.find_one({"session_id": event.session_id})
            if txn and not txn.get("activated"):
                plan_name = event.metadata.get("plan", "pro")
                plan = SUBSCRIPTION_PLANS.get(plan_name, SUBSCRIPTION_PLANS["pro"])
                exp_days = plan.get("expiration_days")

                await db.users.update_one(
                    {"id": event.metadata.get("user_id")},
                    {"$set": {
                        "account_type": plan_name,
                        "subscription_plan": plan_name,
                        "subscription_activated_at": datetime.utcnow()
                    }}
                )

                update_fields = {"account_type": plan_name}
                if exp_days:
                    update_fields["expires_at"] = datetime.utcnow() + timedelta(days=exp_days)
                else:
                    update_fields["expires_at"] = None
                await db.notepads.update_many(
                    {"user_id": event.metadata.get("user_id")},
                    {"$set": update_fields}
                )

                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"activated": True, "payment_status": "paid"}}
                )
        return {"status": "ok"}
    except Exception as e:
        logging.getLogger(__name__).error(f"Webhook error: {e}")
        return {"status": "error"}


# --- Admin Stats ---

@api_router.post("/admin/cleanup-expired")
async def cleanup_expired_notepads():
    """Admin endpoint to cleanup expired notepads"""
    now = datetime.utcnow()
    result = await db.notepads.delete_many({
        "expires_at": {"$lt": now},
        "account_type": {"$in": ["guest", "user"]}
    })
    return {
        "message": f"Cleaned up {result.deleted_count} expired notepads",
        "deleted_count": result.deleted_count
    }


@api_router.get("/admin/stats")
async def get_stats():
    """Get notepad statistics"""
    total = await db.notepads.count_documents({})
    guest = await db.notepads.count_documents({"account_type": "guest"})
    user_notepads = await db.notepads.count_documents({"account_type": "user"})
    total_users = await db.users.count_documents({})
    
    now = datetime.utcnow()
    expiring_soon = await db.notepads.count_documents({
        "expires_at": {
            "$gt": now,
            "$lt": now + timedelta(days=EXPIRATION_WARNING_DAYS)
        }
    })
    expired = await db.notepads.count_documents({
        "expires_at": {"$lt": now}
    })
    
    return {
        "total_notepads": total,
        "guest_notepads": guest,
        "user_notepads": user_notepads,
        "total_users": total_users,
        "expiring_soon": expiring_soon,
        "expired_awaiting_cleanup": expired
    }


# ==================== Web Pages ====================

@api_router.get("/", response_class=HTMLResponse)
async def landing_page():
    """Landing page where users enter their code"""
    html_content = '''<!DOCTYPE html>
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
            var code = document.getElementById('codeInput').value.trim().toLowerCase();
            var errorEl = document.getElementById('error');
            if (!code) { errorEl.textContent = 'Please enter a code'; errorEl.classList.add('show'); return; }
            errorEl.classList.remove('show');
            try {
                var response = await fetch('/api/notepad/lookup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: code }) });
                if (response.ok) { window.location.href = '/api/notepad/' + code + '/view'; }
                else { 
                    var data = await response.json(); 
                    if (response.status === 410) {
                        errorEl.textContent = 'This notepad has expired. Guest notepads are available for 90 days.';
                    } else {
                        errorEl.textContent = data.detail || 'Notepad not found.'; 
                    }
                    errorEl.classList.add('show'); 
                }
            } catch (err) { errorEl.textContent = 'Connection error. Please try again.'; errorEl.classList.add('show'); }
        }
        document.getElementById('codeInput').focus();
    </script>
</body>
</html>'''
    return HTMLResponse(content=html_content)


@api_router.get("/notepad/{code}/view", response_class=HTMLResponse)
async def view_notepad(code: str):
    """Web view of notepad"""
    notepad = await db.notepads.find_one({"code": code.lower()})
    if not notepad:
        return HTMLResponse(
            content='''<!DOCTYPE html><html><head><title>Not Found</title>
            <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0f0f1a;color:#fff;}
            .container{text-align:center;}h1{color:#ef4444;}a{color:#60a5fa;}</style></head>
            <body><div class="container"><h1>Notepad not found</h1><p>Check your code and try again.</p>
            <p><a href="/api/">← Back to home</a></p></div></body></html>''',
            status_code=404
        )

    # Send push notification to notepad owner
    owner_id = notepad.get("user_id")
    if owner_id:
        owner = await db.users.find_one({"id": owner_id})
        if owner:
            for push_token in owner.get("push_tokens", []):
                asyncio.create_task(send_push_notification(
                    push_token,
                    "Notepad Viewed",
                    f"Someone is viewing your notepad '{code}'",
                    {"code": code, "event": "view"}
                ))
    
    expires_at = notepad.get("expires_at")
    if expires_at and is_expired(expires_at):
        return HTMLResponse(
            content='''<!DOCTYPE html><html><head><title>Expired</title>
            <style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0f0f1a;color:#fff;}
            .container{text-align:center;max-width:400px;}.icon{font-size:4rem;margin-bottom:16px;}h1{color:#f59e0b;margin-bottom:12px;}
            p{color:#a1a1aa;margin-bottom:8px;}a{color:#60a5fa;}</style></head>
            <body><div class="container"><div class="icon">⏰</div><h1>Notepad Expired</h1>
            <p>This notepad has expired. Guest notepads are available for 90 days.</p>
            <p>Create a new notepad from the app to continue.</p>
            <p><a href="/api/">← Back to home</a></p></div></body></html>''',
            status_code=410
        )
    
    notepad_code = notepad.get("code")
    account_type = notepad.get("account_type", "guest")
    
    if expires_at is None and account_type != "premium":
        created_at = notepad.get("created_at", datetime.utcnow())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        if account_type == "user":
            expires_at = created_at + timedelta(days=USER_EXPIRATION_DAYS)
        else:
            expires_at = created_at + timedelta(days=GUEST_EXPIRATION_DAYS)
    
    days_remaining = calculate_days_remaining(expires_at) if expires_at else None
    is_expiring_soon = days_remaining is not None and days_remaining <= EXPIRATION_WARNING_DAYS
    
    if expires_at:
        expiration_date_str = expires_at.strftime("%B %d, %Y")
        if is_expiring_soon:
            expiration_banner = f'''<div class="expiration-banner warning">
                <span class="expiration-icon">⚠️</span>
                <span>Expires in {days_remaining} day{"s" if days_remaining != 1 else ""} ({expiration_date_str})</span>
            </div>'''
        else:
            expiration_banner = f'''<div class="expiration-banner">
                <span class="expiration-icon">📅</span>
                <span>Expires {expiration_date_str} ({days_remaining} days)</span>
            </div>'''
    else:
        expiration_banner = '''<div class="expiration-banner premium">
            <span class="expiration-icon">⭐</span>
            <span>Premium notepad - Never expires</span>
        </div>'''
    
    entries_html = ""
    for entry in reversed(notepad.get("entries", [])):
        timestamp = entry.get("timestamp", datetime.utcnow())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = timestamp.strftime("%H:%M:%S")
        text = entry.get("text", "")
        text_display = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("\n", "<br>")
        text_data = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
        entries_html += f'''<div class="entry">
            <div class="entry-header">
                <span class="timestamp">{time_str}</span>
                <button class="copy-btn" data-text="{text_data}" onclick="copyFromData(this)">Copy</button>
            </div>
            <div class="text">{text_display}</div>
        </div>'''
    
    if not entries_html:
        entries_html = '''<div class="empty" id="emptyState">
            <div class="empty-icon">📋</div>
            <p>No entries yet</p>
            <p style="font-size: 0.9rem; color: #52525b;">Copy text on your phone and tap the capture button</p>
        </div>'''
    
    entry_count = len(notepad.get("entries", []))
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PasteBridge - {notepad_code}</title>
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
            margin-bottom: 16px;
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
        .expiration-banner {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            font-size: 0.85rem;
            color: #a1a1aa;
            margin-bottom: 16px;
        }}
        .expiration-banner.warning {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}
        .expiration-banner.premium {{
            background: rgba(168, 85, 247, 0.15);
            color: #c084fc;
            border: 1px solid rgba(168, 85, 247, 0.3);
        }}
        .expiration-icon {{ font-size: 1rem; }}
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
        .summarize-section {{ margin: 20px 0; }}
        .summarize-btn {{
            background: linear-gradient(135deg, #8b5cf6, #6366f1);
            border: none; color: white; padding: 10px 20px; border-radius: 10px;
            font-size: 0.9rem; font-weight: 600; cursor: pointer; display: inline-flex;
            align-items: center; gap: 8px; transition: opacity 0.2s;
        }}
        .summarize-btn:hover {{ opacity: 0.85; }}
        .summarize-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .summary-box {{
            background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.25);
            border-radius: 12px; padding: 20px; margin-top: 12px; display: none;
            line-height: 1.6; color: #d4d4d8; font-size: 0.95rem; white-space: pre-wrap;
        }}
        .summary-box.show {{ display: block; }}
        .export-btns {{ display: flex; gap: 8px; margin: 16px 0; flex-wrap: wrap; }}
        .export-btn {{
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            color: #a1a1aa; padding: 6px 14px; border-radius: 8px; font-size: 0.8rem;
            cursor: pointer; text-decoration: none; transition: all 0.2s;
        }}
        .export-btn:hover {{ background: rgba(255,255,255,0.15); color: #e4e4e7; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <h1>PasteBridge</h1>
                <div class="code-badge">🔗 {notepad_code}</div>
            </div>
            <div class="stats">
                <div class="count" id="entryCount">{entry_count}</div>
                <div class="label">entries</div>
            </div>
        </div>
        {expiration_banner}
        <div class="export-btns">
            <a href="/api/notepad/{notepad_code}/export?format=txt" class="export-btn" download>Export TXT</a>
            <a href="/api/notepad/{notepad_code}/export?format=md" class="export-btn" download>Export MD</a>
            <a href="/api/notepad/{notepad_code}/export?format=json" class="export-btn" download>Export JSON</a>
        </div>
        <div class="summarize-section">
            <button class="summarize-btn" id="summarizeBtn" onclick="summarizeNotepad()">AI Summarize</button>
            <div class="summary-box" id="summaryBox"></div>
        </div>
        <div class="status">
            <span class="dot"></span>
            <span id="statusText">Live updating</span>
        </div>
        <div class="entries" id="entriesContainer">
            {entries_html}
        </div>
        <a href="/api/" class="back-link">← Enter different code</a>
    </div>
    <script>
        var CODE = '{notepad_code}';
        var lastCount = {entry_count};
        
        function copyFromData(btn) {{
            var text = btn.getAttribute('data-text');
            navigator.clipboard.writeText(text).then(function() {{
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(function() {{
                    btn.textContent = 'Copy';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}
        
        function escapeHtml(str) {{
            var div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }}
        
        function escapeAttr(str) {{
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }}
        
        function formatTime(ts) {{
            var d = new Date(ts);
            return d.toLocaleTimeString('en-US', {{ hour12: false }});
        }}
        
        function renderEntries(entries) {{
            var container = document.getElementById('entriesContainer');
            var countEl = document.getElementById('entryCount');
            countEl.textContent = entries.length;
            
            if (entries.length === 0) {{
                container.innerHTML = '<div class="empty"><div class="empty-icon">📋</div><p>No entries yet</p><p style="font-size:0.9rem;color:#52525b;">Copy text on your phone and tap the capture button</p></div>';
                return;
            }}
            
            if (entries.length !== lastCount) {{
                var html = '';
                for (var i = entries.length - 1; i >= 0; i--) {{
                    var entry = entries[i];
                    var textDisplay = escapeHtml(entry.text).replace(/\\n/g, '<br>');
                    var textData = escapeAttr(entry.text);
                    html += '<div class="entry"><div class="entry-header"><span class="timestamp">' + formatTime(entry.timestamp) + '</span><button class="copy-btn" data-text="' + textData + '" onclick="copyFromData(this)">Copy</button></div><div class="text">' + textDisplay + '</div></div>';
                }}
                container.innerHTML = html;
                lastCount = entries.length;
            }}
        }}
        
        function poll() {{
            fetch('/api/notepad/' + CODE)
                .then(function(r) {{ 
                    if (r.status === 410) {{
                        document.getElementById('statusText').textContent = 'Notepad expired';
                        return null;
                    }}
                    return r.json(); 
                }})
                .then(function(data) {{
                    if (data) {{
                        renderEntries(data.entries);
                        document.getElementById('statusText').textContent = 'Live updating';
                    }}
                }})
                .catch(function() {{
                    document.getElementById('statusText').textContent = 'Reconnecting...';
                }});
        }}
        
        setInterval(poll, 3000);
        
        async function summarizeNotepad() {{
            var btn = document.getElementById('summarizeBtn');
            var box = document.getElementById('summaryBox');
            btn.disabled = true;
            btn.textContent = 'Summarizing...';
            box.className = 'summary-box show';
            box.textContent = 'Analyzing content with AI...';
            try {{
                var r = await fetch('/api/notepad/' + CODE + '/summarize', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{max_length: 500}})
                }});
                var d = await r.json();
                if (r.ok) {{
                    box.textContent = d.summary;
                }} else {{
                    box.textContent = d.detail || 'Summarization failed';
                }}
            }} catch(e) {{
                box.textContent = 'Error connecting to AI service';
            }}
            btn.disabled = false;
            btn.textContent = 'AI Summarize';
        }}
    </script>
</body>
</html>'''
    
    return HTMLResponse(content=html_content)


@api_router.get("/health")
async def health():
    return {"status": "healthy", "service": "PasteBridge API"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def start_cron():
    """Start background cleanup cron job"""
    asyncio.create_task(cleanup_cron())
    logging.getLogger("cron").info("Cleanup cron job started (every 6 hours)")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
