import httpx
from typing import Optional, List, Dict, Any
from app.config import settings


class DashScopeClient:
    """Client for DashScope API (Qwen models) with OpenAI-compatible interface."""
    
    def __init__(self):
        self.api_key = settings.dashscope_api_key
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = "qwen-plus"
        self.timeout = 30.0
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Send chat completion request to DashScope.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions for function calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        
        Returns:
            Dict with 'content', 'tool_calls' (if any), 'finish_reason'
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        choice = data["choices"][0]
        message = choice["message"]
        
        result = {
            "content": message.get("content", ""),
            "finish_reason": choice.get("finish_reason", "stop"),
            "tool_calls": []
        }
        
        # Extract tool calls if present
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                result["tool_calls"].append({
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                })
        
        return result
    
    async def extract_json(
        self,
        system_prompt: str,
        user_message: str,
        json_schema_description: str
    ) -> Dict[str, Any]:
        """
        Extract structured JSON from LLM response.
        Useful for qualification extraction.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_message}\n\nReturn ONLY valid JSON matching this schema: {json_schema_description}"}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            temperature=0.1  # Low temperature for structured output
        )
        
        import json
        try:
            # Try to parse the content as JSON
            content = response["content"].strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}")


llm_client = DashScopeClient()
