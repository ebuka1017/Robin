from fastapi import WebSocket, WebSocketDisconnect
from typing import AsyncGenerator
import asyncio
from app.utils.logger import logger
from app.services.bedrock_streaming import bedrock
from app.services.dynamodb import db
from app.services.redis_cache import cache

class WebSocketHandler:
    def __init__(self):
        self.active_connections = {}
    
    async def handle_audio_stream(self, websocket: WebSocket, session_id: str):
        """Handle bidirectional audio streaming"""
        
        await websocket.accept()
        logger.info("WebSocket connected", session_id=session_id)
        
        # Mark session as active
        cache.set(f"session_active:{session_id}", True, 600)
        
        try:
            # Create async generator for audio input
            async def audio_input_stream() -> AsyncGenerator[bytes, None]:
                while True:
                    try:
                        # Receive audio from client
                        data = await websocket.receive()
                        
                        if 'bytes' in data:
                            yield data['bytes']
                        elif 'text' in data:
                            # Handle control messages
                            import json
                            control = json.loads(data['text'])
                            if control.get('type') == 'end':
                                break
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error("Audio receive error", session_id=session_id, error=str(e))
                        break
            
            # Start bidirectional streaming with Bedrock
            await bedrock.stream_conversation(
                session_id=session_id,
                audio_input_stream=audio_input_stream(),
                websocket=websocket
            )
        
        except WebSocketDisconnect:
            logger.info("Client disconnected", session_id=session_id)
        except Exception as e:
            logger.error("WebSocket error", session_id=session_id, error=str(e))
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        finally:
            # Update session state
            db.update_session_state(session_id, "ended")
            cache.delete(f"session_active:{session_id}")
            logger.info("Session ended", session_id=session_id)

ws_handler = WebSocketHandler()
