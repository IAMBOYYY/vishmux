#!/usr/bin/env python3
"""
VISHMUX Planner – simple rule-based intent detection for user messages.
"""

from typing import Optional


class Planner:
    """
    Analyzes user messages to detect intent and determine which tools
    might be needed for the conversation.
    """

    # Keyword sets for intent detection
    WEB_KEYWORDS = [
        "search", "find", "latest", "news", "look up",
        "what is", "who is", "current", "today", "google",
    ]

    FILE_KEYWORDS = [
        "file", "read", "open", "analyze", "pdf", "document",
        "edit", "modify", "write to",
    ]

    CODE_KEYWORDS = [
        "create", "build", "make", "write code", "generate",
        "website", "script", "program", "app", "function",
        "implement", "code", "debug", "fix this code",
    ]

    PHONE_KEYWORDS = [
        "open app", "send message", "call", "screenshot",
        "control", "phone", "sms", "whatsapp",
    ]

    QUESTION_WORDS = [
        "what", "why", "how", "when", "where", "who", "which",
        "can you", "could you", "would you", "do you", "is it",
        "are there", "should i", "will this",
    ]

    def detect_intent(self, message: str) -> dict:
        """
        Analyze a user message and return a dictionary of detected intents.
        """
        message_lower = message.strip().lower()

        intent = {
            "needs_web_search": False,
            "needs_file": False,
            "needs_code": False,
            "needs_phone": False,
            "is_question": False,
            "is_task": False,
        }

        # Check for web search intent
        for kw in self.WEB_KEYWORDS:
            if kw in message_lower:
                intent["needs_web_search"] = True
                break

        # Check for file operations
        for kw in self.FILE_KEYWORDS:
            if kw in message_lower:
                intent["needs_file"] = True
                break

        # Check for code generation
        for kw in self.CODE_KEYWORDS:
            if kw in message_lower:
                intent["needs_code"] = True
                break

        # Check for phone control
        for kw in self.PHONE_KEYWORDS:
            if kw in message_lower:
                intent["needs_phone"] = True
                break

        # Check if it's a question
        if message.rstrip().endswith("?"):
            intent["is_question"] = True
        else:
            for word in self.QUESTION_WORDS:
                if message_lower.startswith(word):
                    intent["is_question"] = True
                    break

        # Check if it's a task (imperative sentence starting with verb)
        if not intent["is_question"]:
            first_word = message_lower.split()[0] if message_lower.split() else ""
            task_verbs = [
                "create", "make", "build", "write", "run", "install",
                "delete", "remove", "copy", "move", "open", "start",
                "show", "tell", "list", "check", "find", "search",
                "generate", "set", "configure", "update", "download",
            ]
            if first_word in task_verbs:
                intent["is_task"] = True

        return intent

    def get_tool_hint(self, intent: dict) -> str:
        """
        Generate a hint string about available tools based on detected intent.
        Returns empty string if no tools are needed.
        """
        hints = []

        if intent["needs_web_search"]:
            hints.append("Web search is available via /web command")
        if intent["needs_file"]:
            hints.append("File operations are supported via /file command")
        if intent["needs_code"]:
            hints.append("You can generate and explain code")
        if intent["needs_phone"]:
            hints.append("Phone control features are available")

        if hints:
            return "Available tools: " + "; ".join(hints) + "."
        return ""

    def requires_tools(self, intent: dict) -> bool:
        """
        Return True if any tool flag is set in the intent dictionary.
        """
        return any([
            intent.get("needs_web_search", False),
            intent.get("needs_file", False),
            intent.get("needs_code", False),
            intent.get("needs_phone", False),
        ])