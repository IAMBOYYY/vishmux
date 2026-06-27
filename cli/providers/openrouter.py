#!/usr/bin/env python3
"""
OpenRouter provider – unified access to 100+ models.
"""

import json
from typing import AsyncGenerator

import httpx
from .base import BaseProvider


class OpenRouterProvider(BaseProvider):
    BASE_URL = "https://openrouter.ai/api/v1"

    def get_name(self) -> str:
        return "OpenRouter"

    async def get_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.get(
                f"{self.BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        models = [item["id"] for item in data.get("data", [])[:50]]
        return models

    async def chat(self, messages: list, stream: bool = True) -> AsyncGenerator[str, None]:
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/IAMBOYYY/vishmux",
            "X-Title": "VISHMUX Agent",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": 4096,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            if stream:
                try:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        response.raise_for_status()
                        async for content in self._stream_response(response):
                            yield content
                except httpx.TimeoutException:
                    raise Exception("Request timed out. Try again.")
                except httpx.HTTPStatusError as e:
                    self._handle_status_error(e)
                except Exception as e:
                    raise Exception(str(e))
            else:
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    yield content
                except httpx.TimeoutException:
                    raise Exception("Request timed out. Try again.")
                except httpx.HTTPStatusError as e:
                    self._handle_status_error(e)
                except Exception as e:
                    raise Exception(str(e))

    def _handle_status_error(self, e: httpx.HTTPStatusError) -> None:
        status = e.response.status_code
        if status == 401:
            raise Exception("Invalid API key.")
        elif status == 429:
            raise Exception("Rate limit hit. Wait a moment.")
        else:
            raise Exception(f"API error {status}")