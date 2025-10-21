import httpx
import time
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logger import logger
from app.services.redis_cache import cache

class GatewayClient:
    def __init__(self):
        self.mcp_url = settings.gateway_mcp_url
        self.client_id = settings.oauth_client_id
        self.client_secret = settings.oauth_client_secret
        self.token_url = settings.oauth_token_url
        self._token = None
        self._token_expires_at = 0
        logger.info("Gateway client initialized", url=self.mcp_url)
    
    def _get_oauth_token(self) -> str:
        """Get OAuth token from cache or fetch new one"""
        cached_token = cache.get("gateway_oauth_token")
        if cached_token:
            return cached_token
        
        try:
            response = httpx.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0
            )
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            
            # Cache token with 5min buffer before expiry
            cache.set("gateway_oauth_token", access_token, expires_in - 300)
            logger.info("OAuth token obtained", expires_in=expires_in)
            return access_token
        
        except Exception as e:
            logger.error("OAuth token fetch failed", error=str(e))
            raise
    
    def _call_mcp(self, method: str, params: Dict = None) -> Dict:
        """Make MCP JSON-RPC call"""
        token = self._get_oauth_token()
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": int(time.time() * 1000)
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = httpx.post(
                self.mcp_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error("MCP error", method=method, error=result["error"])
                raise Exception(f"MCP error: {result['error']}")
            
            return result.get("result", {})
        
        except Exception as e:
            logger.error("MCP call failed", method=method, error=str(e))
            raise
    
    def list_tools(self) -> List[Dict]:
        """Get available tools from Gateway"""
        cached_tools = cache.get("gateway_tools_list")
        if cached_tools:
            return cached_tools
        
        result = self._call_mcp("tools/list")
        tools = result.get("tools", [])
        
        # Cache for 1 hour
        cache.set("gateway_tools_list", tools, 3600)
        logger.info("Tools listed", count=len(tools))
        return tools
    
    def invoke_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Invoke a specific tool"""
        start_time = time.time()
        
        try:
            result = self._call_mcp("tools/invoke", {
                "name": tool_name,
                "arguments": arguments
            })
            
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info("Tool invoked", tool=tool_name, latency_ms=latency_ms)
            
            return {
                "success": True,
                "result": result,
                "latency_ms": latency_ms
            }
        
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("Tool invocation failed", tool=tool_name, error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms
            }
    
    def get_tool_definitions(self) -> List[Dict]:
        """Get tool definitions formatted for Bedrock function calling"""
        tools = self.list_tools()
        
        # Convert MCP tools to Bedrock tool format
        bedrock_tools = []
        for tool in tools:
            bedrock_tools.append({
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "inputSchema": {
                        "json": tool.get("inputSchema", {})
                    }
                }
            })
        
        return bedrock_tools

gateway = GatewayClient()
