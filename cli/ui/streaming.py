#!/usr/bin/env python3
"""
VISHMUX StreamHandler – manages streaming AI responses.
"""

import re
from rich.console import Console
from rich.markdown import Markdown
from .display import Display

console = Console()


class StreamHandler:
    """Handles streaming tokens from providers and markdown rendering."""

    def __init__(self, display: Display):
        self.display = display
        self.buffer = ""

    async def stream_response(self, provider, messages: list) -> str:
        """
        Stream a response from provider and return the full text.
        After streaming, re-renders markdown if detected.
        """
        full_response = ""
        self.buffer = ""

        self.display.stream_start()

        try:
            async for chunk in provider.chat(messages, stream=True):
                self.display.stream_chunk(chunk)
                full_response += chunk
                self.buffer += chunk
        except Exception as e:
            self.display.stream_end()
            raise e

        self.display.stream_end()

        # If the response contains markdown, re-print it formatted
        if self._contains_markdown(full_response):
            console.print()
            console.print(Markdown(full_response))

        return full_response

    def _contains_markdown(self, text: str) -> bool:
        """Check if text contains markdown that should be rendered."""
        patterns = [
            r'^#{1,6}\s',       # headers
            r'```',             # code blocks
            r'^\s*[-*+]\s',     # bullet lists
            r'^\s*\d+\.\s',     # numbered lists
            r'\*\*.*?\*\*',     # bold
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False
