import boto3
import time
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logger import logger

class DynamoDBService:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
        self.sessions_table = self.dynamodb.Table(settings.dynamodb_sessions_table)
        self.messages_table = self.dynamodb.Table(settings.dynamodb_messages_table)
        self.tools_table = self.dynamodb.Table(settings.dynamodb_tools_table)
        logger.info("DynamoDB service initialized")
    
    def create_session(self, session_id: str, user_id: Optional[str] = None) -> Dict:
        start_time = int(time.time() * 1000)
        expires_at = int(time.time()) + (settings.session_ttl_hours * 3600)
        
        item = {
            'session_id': session_id,
            'start_time': start_time,
            'user_id': user_id or 'anonymous',
            'state': 'active',
            'expires_at': expires_at,
            'last_updated': start_time,
            'metadata': {}
        }
        
        self.sessions_table.put_item(Item=item)
        logger.info("Session created", session_id=session_id)
        return item
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        try:
            response = self.sessions_table.query(
                KeyConditionExpression='session_id = :sid',
                ExpressionAttributeValues={':sid': session_id},
                ScanIndexForward=False,
                Limit=1
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except Exception as e:
            logger.error("Get session error", session_id=session_id, error=str(e))
            return None
    
    def update_session_state(self, session_id: str, state: str):
        start_time = self.get_session(session_id)['start_time']
        self.sessions_table.update_item(
            Key={'session_id': session_id, 'start_time': start_time},
            UpdateExpression='SET #state = :state, last_updated = :ts',
            ExpressionAttributeNames={'#state': 'state'},
            ExpressionAttributeValues={
                ':state': state,
                ':ts': int(time.time() * 1000)
            }
        )
    
    def add_message(self, session_id: str, role: str, text: str, tool_call: Optional[Dict] = None):
        ts_message = int(time.time() * 1000)
        expires_at = int(time.time()) + (settings.session_ttl_hours * 3600)
        
        item = {
            'session_id': session_id,
            'ts_message': ts_message,
            'role': role,
            'text': text,
            'expires_at': expires_at
        }
        
        if tool_call:
            item['tool_call'] = tool_call
        
        self.messages_table.put_item(Item=item)
    
    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict]:
        response = self.messages_table.query(
            KeyConditionExpression='session_id = :sid',
            ExpressionAttributeValues={':sid': session_id},
            ScanIndexForward=True,
            Limit=limit
        )
        return response.get('Items', [])
    
    def add_tool_call(self, session_id: str, tool_name: str, input_data: Dict, output_data: Dict, latency_ms: int, status: str):
        ts_toolcall = int(time.time() * 1000)
        expires_at = int(time.time()) + (settings.session_ttl_hours * 3600)
        
        item = {
            'session_id': session_id,
            'ts_toolcall': ts_toolcall,
            'tool_name': tool_name,
            'input': input_data,
            'output': output_data,
            'latency_ms': latency_ms,
            'status': status,
            'expires_at': expires_at
        }
        
        self.tools_table.put_item(Item=item)
    
    def get_tool_calls(self, session_id: str, limit: int = 50) -> List[Dict]:
        response = self.tools_table.query(
            KeyConditionExpression='session_id = :sid',
            ExpressionAttributeValues={':sid': session_id},
            ScanIndexForward=False,
            Limit=limit
        )
        return response.get('Items', [])

db = DynamoDBService()
