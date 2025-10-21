import redis
import json
from typing import Optional, Any
from app.config import settings
from app.utils.logger import logger

class RedisCache:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True,
            socket_connect_timeout=5
        )
        logger.info("Redis cache initialized", host=settings.redis_host)
    
    def get(self, key: str) -> Optional[Any]:
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        try:
            self.client.setex(key, ttl_seconds, json.dumps(value))
            return True
        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False
    
    def delete(self, key: str):
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False
    
    def exists(self, key: str) -> bool:
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error("Redis exists error", key=key, error=str(e))
            return False

cache = RedisCache()
