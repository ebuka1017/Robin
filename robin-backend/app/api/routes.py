from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
import time
from app.services.dynamodb import db
from app.services.redis_cache import cache
from app.utils.logger import logger

router = APIRouter()

class SessionStartRequest(BaseModel):
    user_id: Optional[str] = None

class SessionStartResponse(BaseModel):
    session_id: str
    websocket_url: str
    created_at: int

class SessionInfo(BaseModel):
    session_id: str
    state: str
    start_time: int
    user_id: str
    last_updated: int

class Message(BaseModel):
    timestamp: int
    role: str
    text: str
    tool_call: Optional[dict] = None

class ToolCall(BaseModel):
    timestamp: int
    tool_name: str
    input: dict
    output: dict
    latency_ms: int
    status: str

@router.post("/sessions/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    """Create a new session"""
    session_id = str(uuid.uuid4())
    
    # Create session in DynamoDB
    session = db.create_session(session_id, request.user_id)
    
    # Cache session
    cache.set(f"session:{session_id}", session, 3600)
    
    logger.info("Session started", session_id=session_id, user_id=request.user_id)
    
    return SessionStartResponse(
        session_id=session_id,
        websocket_url=f"ws://localhost:8000/ws/audio?session_id={session_id}",
        created_at=session['start_time']
    )

@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get session metadata"""
    
    # Try cache first
    cached = cache.get(f"session:{session_id}")
    if cached:
        return SessionInfo(**cached)
    
    # Fetch from DynamoDB
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Cache it
    cache.set(f"session:{session_id}", session, 3600)
    
    return SessionInfo(**session)

@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str):
    """End a session gracefully"""
    
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update state
    db.update_session_state(session_id, "ended")
    
    # Remove from cache
    cache.delete(f"session:{session_id}")
    cache.delete(f"session_active:{session_id}")
    
    logger.info("Session ended via API", session_id=session_id)
    
    return {"status": "ended", "session_id": session_id}

@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Check if session is active"""
    
    # Check cache for active status
    is_active = cache.exists(f"session_active:{session_id}")
    
    if is_active:
        return {"session_id": session_id, "status": "active"}
    
    # Check DynamoDB
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"session_id": session_id, "status": session['state']}

@router.get("/history/{session_id}")
async def get_conversation_history(session_id: str, limit: int = 50):
    """Get conversation history for a session"""
    
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = db.get_messages(session_id, limit)
    
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "messages": [Message(**msg) for msg in messages]
    }

@router.get("/tools/calls")
async def get_tool_calls(session_id: str, limit: int = 50):
    """Get tool call history"""
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    tool_calls = db.get_tool_calls(session_id, limit)
    
    return {
        "session_id": session_id,
        "tool_call_count": len(tool_calls),
        "tool_calls": [ToolCall(**tc) for tc in tool_calls]
    }

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": int(time.time() * 1000)
    }
