#!/usr/bin/env python3
"""
Google Gemini provider – handles native Gemini API format.
"""

import json
from typing import AsyncGenerator

import httpx
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def get_name(self) -> str:
        return "Google Gemini"

    async def get_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.get(
                f"{self.BASE_URL}/models?key={self.api_key}"
            )
            resp.raise_for_status()
            data = resp.json()
        models = []
        for item in data.get("models", []):
            name = item.get("name", "")
            if name.startswith("models/"):
                name = name[7:]
            if "gemini" in name.lower():
                models.append(name)
        return models

    def _convert_messages(self, messages: list) -> list:
        """
        Convert OpenAI-style messages to Gemini contents.
        System message is prepended as a user message with its text.
        """
        system_prompt = None
        converted = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content  # store and handle later
                continue
            elif role == "user":
                converted.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                converted.append({"role": "model", "parts": [{"text": content}]})
            # ignore other roles (like "function") for now

        if system_prompt:
            # prepend system prompt as a user message
            converted.insert(0, {"role": "user", "parts": [{"text": system_prompt}]})
        return converted

    async def chat(self, messages: list, stream: bool = True) -> AsyncGenerator[str, None]:
        gemini_contents = self._convert_messages(messages)

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            if stream:
                url = f"{self.BASE_URL}/models/{self.model}:streamGenerateContent?key={self.api_key}&alt=sse"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": gemini_contents}
                try:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                try:
                                    chunk = json.loads(data_str)
                                    candidates = chunk.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        if parts and "text" in parts[0]:
                                            yield parts[0]["text"]
                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
                except httpx.TimeoutException:
                    raise Exception("Request timed out. Try again.")
                except httpx.HTTPStatusError as e:
                    self._handle_status_error(e)
                except Exception as e:
                    raise Exception(str(e))
            else:
                url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": gemini_contents}
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            yield parts[0]["text"]
                except httpx.TimeoutException:
                    raise Exception("Request timed out. Try again.")
                except httpx.HTTPStatusError as e:
                    self._handle_status_error(e)
                except Exception as e:
                    raise Exception(str(e))

    def _handle_status_error(self, e: httpx.HTTPStatusError) -> None:
        status = e.response.status_code
        if status == 401 or status == 403:
            raise Exception("Invalid API key.")
        elif status == 429:
            raise Exception("Rate limit hit. Wait a moment.")
        else:
            raise Exception(f"API error {status}")