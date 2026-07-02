#!/usr/bin/env python3
"""
Anthropic provider – Claude models using Anthropic's native API.
"""

import json
from typing import AsyncGenerator, Optional

import httpx
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    BASE_URL = "https://api.anthropic.com/v1"

    def get_name(self) -> str:
        return "Anthropic"

    async def get_models(self) -> list[str]:
        # Hardcoded list – no API call needed
        return [
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ]

    def _extract_system_prompt(self, messages: list) -> tuple[Optional[str], list]:
        """Separate system message from the conversation."""
        system_prompt = None
        filtered = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                filtered.append(msg)
        return system_prompt, filtered

    async def chat(self, messages: list, stream: bool = True) -> AsyncGenerator[str, None]:
        system_prompt, conversation = self._extract_system_prompt(messages)
        url = f"{self.BASE_URL}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": conversation,
            "stream": stream,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            if stream:
                try:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                try:
                                    event = json.loads(data_str)
                                    event_type = event.get("type")
                                    if event_type == "content_block_delta":
                                        delta = event.get("delta", {})
                                        text = delta.get("text", "")
                                        if text:
                                            yield text
                                    elif event_type == "message_stop":
                                        break
                                except (json.JSONDecodeError, KeyError):
                                    continue
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
                    content_blocks = data.get("content", [])
                    if content_blocks and "text" in content_blocks[0]:
                        yield content_blocks[0]["text"]
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

    async def chat_with_tools(self, messages: list, tools: list) -> dict:
        """Tool calling not yet implemented for this provider."""
        return {
            "success": False,
            "error": "Tool use isn't wired up for this provider yet. Switch to Groq, OpenRouter, Nvidia, Together, or Mistral to use agent tools (switch → pick provider).",
            "content": None,
            "tool_calls": [],
        }
