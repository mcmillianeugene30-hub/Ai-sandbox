import requests
import json
from typing import List, Dict, Any, Optional, Generator

class AISandboxClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.chat = Chat(self)

class Chat:
    def __init__(self, client: AISandboxClient):
        self.client = client

    def completions(self, provider: str, model: str, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Any:
        url = f"{self.client.base_url}/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.client.api_key
        }
        payload = {
            "provider": provider,
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=stream)
        if response.status_code != 200:
            raise Exception(f"AI Sandbox Error: {response.text}")
        
        if stream:
            def gen():
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            yield data
            return gen()
        
        return response.json()
