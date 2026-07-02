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

    async def chat_with_tools(self, messages: list, tools: list) -> dict:
        """
        Non-streaming chat call that includes tool/function definitions,
        for OpenAI-compatible providers. Subclasses that use a different
        API shape (Anthropic, Gemini) must override this method.

        `tools` is a list of dicts already in OpenAI tool-schema format:
        [{"type": "function", "function": {"name": ..., "description": ...,
          "parameters": {...}}}, ...]

        Returns a dict with this exact shape:
        {
            "success": True,
            "content": "<final text, or None if the model only returned tool calls>",
            "tool_calls": [
                {"id": "<call id from API>", "name": "<function name>",
                 "arguments": {<parsed dict, NOT a json string>}}
            ]  # empty list if no tool calls
        }
        On any failure:
        {"success": False, "error": "<message>", "content": None, "tool_calls": []}
        """
        # Ensure BASE_URL exists
        if not hasattr(self, "BASE_URL"):
            return {
                "success": False,
                "error": "This provider does not support tool calling yet.",
                "content": None,
                "tool_calls": [],
            }
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                message = data["choices"][0]["message"]
                content = message.get("content")  # may be None
                raw_tool_calls = message.get("tool_calls") or []
                tool_calls = []
                for tc in raw_tool_calls:
                    tc_id = tc.get("id", "")
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        args = {}
                        tool_calls.append({
                            "id": tc_id,
                            "name": name,
                            "arguments": {},
                            "parse_error": "Could not parse arguments",
                        })
                        continue
                    tool_calls.append({
                        "id": tc_id,
                        "name": name,
                        "arguments": args,
                    })
                return {
                    "success": True,
                    "content": content,
                    "tool_calls": tool_calls,
                }
        except AttributeError:
            return {
                "success": False,
                "error": "This provider does not support tool calling yet.",
                "content": None,
                "tool_calls": [],
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Request timed out. Try again.",
                "content": None,
                "tool_calls": [],
            }
        except httpx.HTTPStatusError as e:
            try:
                self._handle_status_error(e)
            except Exception as exc:
                return {
                    "success": False,
                    "error": str(exc),
                    "content": None,
                    "tool_calls": [],
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "tool_calls": [],
            }
