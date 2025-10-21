from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.websocket import ws_handler
from app.config import settings
from app.utils.logger import logger

app = FastAPI(
    title="Robin Voice Agent API",
    description="Backend API for Robin AI Voice Assistant",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST API routes
app.include_router(router, prefix="/api", tags=["api"])

# WebSocket endpoint
@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for bidirectional audio streaming"""
    await ws_handler.handle_audio_stream(websocket, session_id)

@app.on_event("startup")
async def startup_event():
    logger.info("Robin backend starting", 
                region=settings.aws_region,
                model=settings.bedrock_model_id)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Robin backend shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level="info"
    )
