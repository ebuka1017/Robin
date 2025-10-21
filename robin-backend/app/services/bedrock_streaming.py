import asyncio
import json
import base64
import uuid
from typing import AsyncGenerator, Dict
from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient, InvokeModelWithBidirectionalStreamOperationInput
from aws_sdk_bedrock_runtime.models import InvokeModelWithBidirectionalStreamInputChunk, BidirectionalInputPayloadPart
from aws_sdk_bedrock_runtime.config import Config
import boto3

from app.config import settings
from app.utils.logger import logger
from app.services.gateway import gateway
from app.services.dynamodb import db

class BedrockStreaming:
    def __init__(self):
        self.model_id = settings.bedrock_model_id
        self.voice = settings.bedrock_voice
        self.client = None
        self._initialize_client()
        logger.info("Bedrock streaming initialized", model=self.model_id)

    def _initialize_client(self):
        """Initialize Bedrock client with Smithy SDK"""
        # The Smithy client will automatically resolve credentials from the environment
        # (e.g., IAM role, ~/.aws/credentials, or environment variables)
        config = Config(
            region=settings.aws_region
        )
        self.client = BedrockRuntimeClient(config=config)

    def get_system_prompt(self) -> str:
        """Your complete Robin system prompt"""
        return """You are Robin, an AI voice assistant for enterprise productivity.

You help users manage their Gmail, Google Calendar, and Slack through natural conversation.

Core Capabilities:
- Email: Search, read, compose, and send emails via Gmail
- Calendar: Query schedule, create events, update meetings
- Slack: Send messages, search conversations, list channels

Personality:
- Professional but friendly
- Concise and action-oriented
- Proactive in suggesting next steps
- Clear about what you're doing (announce tool usage)

Guidelines:
- Always confirm before sending emails or messages
- Announce when you're checking emails, calendar, or Slack
- Provide clear summaries of results
- Ask clarifying questions if intent is unclear
- Be conversational and natural in speech

When using tools:
1. Announce what you're doing: "Let me check your emails..."
2. Execute the tool
3. Summarize results clearly
4. Suggest next actions if relevant

Remember: You communicate through voice. Keep responses concise and natural for spoken conversation."""

    async def stream_conversation(
        self,
        session_id: str,
        audio_input_stream: AsyncGenerator[bytes, None],
        websocket
    ):
        """Handle bidirectional streaming with Nova Sonic"""

        prompt_name = str(uuid.uuid4())
        content_name = str(uuid.uuid4())
        audio_content_name = str(uuid.uuid4())

        # Get tool definitions from Gateway
        tools = gateway.get_tool_definitions()

        # Start stream
        stream_response = await self.client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_id)
        )

        # Send initialization events
        await self._send_session_start(stream_response)
        await self._send_prompt_start(stream_response, prompt_name, tools)
        await self._send_system_prompt(stream_response, prompt_name, content_name)

        # Start audio content
        await self._send_audio_content_start(stream_response, prompt_name, audio_content_name)

        # Process input and output concurrently
        input_task = asyncio.create_task(
            self._process_audio_input(stream_response, audio_input_stream, prompt_name, audio_content_name)
        )
        output_task = asyncio.create_task(
            self._process_output_events(stream_response, session_id, websocket, prompt_name)
        )

        try:
            await asyncio.gather(input_task, output_task)
        except Exception as e:
            logger.error("Streaming error", session_id=session_id, error=str(e))
        finally:
            # Gracefully end the stream
            if not input_task.done():
                input_task.cancel()
            if not output_task.done():
                output_task.cancel()
            
            await self._send_audio_content_end(stream_response, prompt_name, audio_content_name)
            await self._send_prompt_end(stream_response, prompt_name)
            await self._send_session_end(stream_response)

    async def _send_raw_event(self, stream_response, event_json: str):
        """Send raw JSON event to stream"""
        event = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=event_json.encode('utf-8'))
        )
        await stream_response.input_stream.send(event)

    async def _send_session_start(self, stream_response):
        """Send session start event"""
        event = {
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": 1024,
                        "topP": 0.9,
                        "temperature": 0.7
                    }
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _send_prompt_start(self, stream_response, prompt_name: str, tools: list):
        """Send prompt start with tools"""
        event = {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": {
                        "mediaType": "text/plain"
                    },
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": 24000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "voiceId": self.voice,
                        "encoding": "base64",
                        "audioType": "SPEECH"
                    },
                    "toolUseOutputConfiguration": {
                        "mediaType": "application/json"
                    },
                    "toolConfiguration": {
                        "tools": tools
                    }
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _send_system_prompt(self, stream_response, prompt_name: str, content_name: str):
        """Send system prompt as text content"""
        event = {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "TEXT",
                    "role": "SYSTEM",
                    "interactive": True,
                    "textInputConfiguration": {
                        "mediaType": "text/plain"
                    }
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

        event = {
            "event": {
                "textInput": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": self.get_system_prompt()
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

        event = {
            "event": {
                "contentEnd": {
                    "promptName": prompt_name,
                    "contentName": content_name
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _send_audio_content_start(self, stream_response, prompt_name: str, content_name: str):
        """Send audio content start"""
        event = {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": 16000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "audioType": "SPEECH",
                        "encoding": "base64"
                    }
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _process_audio_input(self, stream_response, audio_stream: AsyncGenerator, prompt_name: str, content_name: str):
        """Send audio chunks to Bedrock"""
        async for audio_chunk in audio_stream:
            if audio_chunk:
                audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                event = {
                    "event": {
                        "audioInput": {
                            "promptName": prompt_name,
                            "contentName": content_name,
                            "content": audio_b64
                        }
                    }
                }
                await self._send_raw_event(stream_response, json.dumps(event))

    async def _process_output_events(self, stream_response, session_id: str, websocket, prompt_name: str):
        """Process output events from Bedrock"""
        tool_use_id = None
        tool_name = None
        tool_content = None

        while True:
            try:
                output = await stream_response.await_output()
                result = await output[1].receive()

                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode('utf-8')
                    json_data = json.loads(response_data)

                    if 'event' not in json_data:
                        continue

                    event = json_data['event']

                    # Audio output
                    if 'audioOutput' in event:
                        audio_b64 = event['audioOutput']['content']
                        audio_bytes = base64.b64decode(audio_b64)
                        await websocket.send_bytes(audio_bytes)

                    # Tool use
                    elif 'toolUse' in event:
                        tool_use_id = event['toolUse']['toolUseId']
                        tool_name = event['toolUse']['toolName']
                        tool_content = event['toolUse']

                        logger.info("Tool use detected", session_id=session_id, tool=tool_name)

                        await websocket.send_json({
                            "type": "tool_call_start",
                            "tool": tool_name,
                            "input": json.loads(tool_content.get('content', '{}'))
                        })

                    # Content end with tool
                    elif 'contentEnd' in event and event['contentEnd'].get('type') == 'TOOL':
                        if tool_name and tool_content:
                            # Invoke tool
                            tool_input = json.loads(tool_content.get('content', '{}'))
                            result = gateway.invoke_tool(tool_name, tool_input)

                            # Log to DynamoDB
                            db.add_tool_call(
                                session_id=session_id,
                                tool_name=tool_name,
                                input_data=tool_input,
                                output_data=result.get("result", {}),
                                latency_ms=result["latency_ms"],
                                status="success" if result["success"] else "failed"
                            )

                            # Send tool result back to Bedrock
                            tool_result_content_name = str(uuid.uuid4())
                            await self._send_tool_result(
                                stream_response, prompt_name, tool_result_content_name,
                                tool_use_id, result.get("result", {})
                            )

                            # Notify frontend
                            await websocket.send_json({
                                "type": "tool_call_end",
                                "tool": tool_name,
                                "result": result.get("result", {}),
                                "latency_ms": result["latency_ms"]
                            })

                    # Text output
                    elif 'textOutput' in event:
                        text = event['textOutput']['content']
                        role = event['textOutput']['role']

                        db.add_message(
                            session_id=session_id,
                            role=role.lower(),
                            text=text
                        )

                    # Completion end
                    elif 'completionEnd' in event:
                        break

            except StopAsyncIteration:
                break
            except Exception as e:
                logger.error("Output processing error", error=str(e))
                break

    async def _send_tool_result(self, stream_response, prompt_name: str, content_name: str, tool_use_id: str, result: Dict):
        """Send tool result back to Bedrock"""
        # Tool content start
        event = {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "interactive": False,
                    "type": "TOOL",
                    "role": "TOOL",
                    "toolResultInputConfiguration": {
                        "toolUseId": tool_use_id,
                        "type": "TEXT",
                        "textInputConfiguration": {
                            "mediaType": "text/plain"
                        }
                    }
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

        # Tool result
        event = {
            "event": {
                "toolResult": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": json.dumps(result)
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

        # Content end
        event = {
            "event": {
                "contentEnd": {
                    "promptName": prompt_name,
                    "contentName": content_name
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _send_audio_content_end(self, stream_response, prompt_name: str, content_name: str):
        event = {
            "event": {
                "contentEnd": {
                    "promptName": prompt_name,
                    "contentName": content_name
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _send_prompt_end(self, stream_response, prompt_name: str):
        event = {
            "event": {
                "promptEnd": {
                    "promptName": prompt_name
                }
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

    async def _send_session_end(self, stream_response):
        event = {
            "event": {
                "sessionEnd": {}
            }
        }
        await self._send_raw_event(stream_response, json.dumps(event))

bedrock = BedrockStreaming()
