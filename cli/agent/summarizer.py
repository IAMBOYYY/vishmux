#!/usr/bin/env python3
"""
VISHMUX Summarizer – smart logging and conversation compression.
"""

import re
from typing import Optional


class Summarizer:
    """
    Creates concise log entries for each exchange and compresses
    conversation history when it grows too large.
    """

    def log_exchange(self, session, user_msg: str, ai_reply: str) -> None:
        """
        Create a smart 1-line summary of the exchange and log it.
        """
        summary = self._make_summary(user_msg, ai_reply)
        session.log_action(summary)

    def _make_summary(self, user_msg: str, ai_reply: str) -> str:
        """Generate a context-aware one-line summary."""
        # Check if AI response contains code
        code_snippet = self.extract_code_snippet(ai_reply)
        if code_snippet:
            return f"Wrote code: {code_snippet[:80]}"

        # Check if user asked a question
        if user_msg.rstrip().endswith("?"):
            shortened = user_msg[:60] + ("..." if len(user_msg) > 60 else "")
            return f"Answered: {shortened}"

        # Check if AI mentioned a file
        if re.search(r'(?:created|saved|wrote|file|path)\b', ai_reply, re.IGNORECASE):
            return f"Created/discussed file"

        # Default chat summary
        shortened = user_msg[:60] + ("..." if len(user_msg) > 60 else "")
        return f"Chat: {shortened}"

    def extract_code_snippet(self, text: str) -> Optional[str]:
        """
        Extract the first line inside a code block (```), or return None.
        """
        # Match first code block and get its first content line
        match = re.search(r'```(?:\w+)?\s*\n(.+?)(?:\n|```)', text, re.DOTALL)
        if match:
            first_line = match.group(1).strip()
            return first_line if first_line else None
        return None

    def compress_history(self, messages: list, max_pairs: int = 15) -> list:
        """
        Keep conversation history manageable by trimming old messages.
        Always preserves system messages at the start.
        """
        # Separate system messages from conversation
        system_msgs = [m for m in messages if m.get("role") == "system"]
        conv_msgs = [m for m in messages if m.get("role") != "system"]

        # Keep last N pairs (each pair = user + assistant)
        max_messages = max_pairs * 2
        if len(conv_msgs) > max_messages:
            conv_msgs = conv_msgs[-max_messages:]

        return system_msgs + conv_msgs