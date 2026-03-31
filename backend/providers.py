import os
import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
import google.generativeai as genai
from groq import Groq
from openai import AsyncOpenAI, OpenAI
import httpx

class AIProvider:
    def chat_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    async def stream_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> AsyncGenerator[str, None]:
        raise NotImplementedError

class GeminiProvider(AIProvider):
    def _convert_messages(self, messages):
        gemini_messages = []
        for m in messages:
            role = 'user' if m['role'] in ['user', 'system'] else 'model'
            gemini_messages.append({'role': role, 'parts': [m['content']]})
        return gemini_messages

    def chat_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(model)
        response = client.generate_content(self._convert_messages(messages))
        return {
            "id": "gemini-res",
            "choices": [{"message": {"role": "assistant", "content": response.text}, "finish_reason": "stop"}],
            "usage": {}
        }

    async def stream_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> AsyncGenerator[str, None]:
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(model)
        response = await client.generate_content_async(self._convert_messages(messages), stream=True)
        async for chunk in response:
            yield json.dumps({"choices": [{"delta": {"content": chunk.text}}]})

class GroqProvider(AIProvider):
    def chat_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(model=model, messages=messages, **kwargs)
        return completion.model_dump()

    async def stream_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> AsyncGenerator[str, None]:
        client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
        stream = await client.chat.completions.create(model=model, messages=messages, stream=True, **kwargs)
        async for chunk in stream:
            yield chunk.model_dump_json()

class OpenRouterProvider(AIProvider):
    def chat_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> Dict[str, Any]:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        completion = client.chat.completions.create(model=model, messages=messages, **kwargs)
        return completion.model_dump()

    async def stream_complete(self, model: str, messages: List[Dict[str, str]], api_key: str, **kwargs) -> AsyncGenerator[str, None]:
        client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        stream = await client.chat.completions.create(model=model, messages=messages, stream=True, **kwargs)
        async for chunk in stream:
            yield chunk.model_dump_json()

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def chat_complete(self, model: str, messages: List[Dict[str, str]], api_key: str = None, **kwargs) -> Dict[str, Any]:
        payload = {"model": model, "messages": messages, "stream": False}
        response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=60.0)
        data = response.json()
        return {
            "choices": [{"message": data['message'], "finish_reason": "stop"}],
            "usage": {}
        }

    async def stream_complete(self, model: str, messages: List[Dict[str, str]], api_key: str = None, **kwargs) -> AsyncGenerator[str, None]:
        payload = {"model": model, "messages": messages, "stream": True}
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=60.0) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        yield json.dumps({"choices": [{"delta": {"content": data['message']['content']}}]})

def get_provider(provider_name: str) -> AIProvider:
    providers = {
        "gemini": GeminiProvider(),
        "groq": GroqProvider(),
        "openrouter": OpenRouterProvider(),
        "ollama": OllamaProvider()
    }
    return providers.get(provider_name.lower())
