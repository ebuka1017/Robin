from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # AWS
    aws_region: str = "us-east-1"
    aws_account_id: str
    
    # Bedrock
    bedrock_model_id: str = "amazon.nova-sonic-v1:0"
    bedrock_voice: str = "tiffany"
    
    # AgentCore Gateway
    gateway_mcp_url: str
    oauth_client_id: str
    oauth_client_secret: str
    oauth_token_url: str
    
    # DynamoDB
    dynamodb_sessions_table: str = "RobinSessions"
    dynamodb_messages_table: str = "RobinSessionMessages"
    dynamodb_tools_table: str = "RobinToolCalls"
    
    # Redis
    redis_host: str
    redis_port: int = 6379
    redis_password: Optional[str] = None
    
    # Session Config
    session_ttl_hours: int = 24
    inactivity_timeout_minutes: int = 10
    
    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    
    # Deployment (optional, for CI/CD)
    ecr_repository: Optional[str] = None
    iam_role_arn: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
