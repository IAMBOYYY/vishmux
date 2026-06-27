#!/usr/bin/env python3
"""
Abstract base class for VISHMUX AI providers.
"""

import json
from typing import AsyncGenerator, Optional

import httpx


class BaseProvider:
    """
    Every provider must implement:
    - chat(messages, stream) → AsyncGenerator[str, None]
    - get_models() → list[str]
    - get_name() → str
    """

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def chat(self, messages: list, stream: bool = True) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Subclasses must implement chat()")

    async def get_models(self) -> list[str]:
        raise NotImplementedError("Subclasses must implement get_models()")

    def get_name(self) -> str:
        raise NotImplementedError("Subclasses must implement get_name()")

    def _handle_status_error(self, e: httpx.HTTPStatusError) -> None:
        """Shared HTTP error handler — all providers use this."""
        status = e.response.status_code
        if status == 401 or status == 403:
            raise Exception("Invalid API key.")
        elif status == 429:
            raise Exception("Rate limit hit. Wait a moment.")
        else:
            raise Exception(f"API error {status}")

    async def _stream_response(self, response: httpx.Response) -> AsyncGenerator[str, None]:
        """
        Generic SSE parser for OpenAI-compatible APIs.
        Yields content chunks from choices[0].delta.content.
        """
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    content = chunk["choices"][0]["delta"].get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
