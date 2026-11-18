"""Server-side chat memory, per session. Kept on the server so a client cannot invent past turns
("Rocco promised me a discount"). In process memory: fine for one Cloud Run instance; several
instances would need a shared store (e.g. Redis or Firestore)."""

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

MAX_TURNS = 6
MAX_CHARS = 2000


@dataclass
class _Conversation:
    turns: list[tuple[str, str]] = field(default_factory=list)
    updated: float = field(default_factory=time.monotonic)


class ConversationStore:
    def __init__(
        self, ttl_seconds: int = 24 * 3600, max_turns: int = MAX_TURNS, max_sessions: int = 2000
    ):
        self.ttl = ttl_seconds
        self.max_turns = max_turns
        self.max_sessions = max_sessions
        self._data: OrderedDict[str, _Conversation] = OrderedDict()
        self._lock = threading.Lock()

    def history(self, session_id: str | None) -> list[tuple[str, str]]:
        """Previous (guest message, assistant reply) pairs, oldest first."""
        if not session_id:
            return []
        with self._lock:
            conversation = self._data.get(session_id)
            if conversation is None:
                return []
            if time.monotonic() - conversation.updated > self.ttl:
                del self._data[session_id]
                return []
            return list(conversation.turns)

    def add(self, session_id: str | None, message: str, reply: str) -> None:
        if not session_id:
            return
        with self._lock:
            conversation = self._data.pop(session_id, None) or _Conversation()
            conversation.turns.append((message[:MAX_CHARS], reply[:MAX_CHARS]))
            conversation.turns = conversation.turns[-self.max_turns :]
            conversation.updated = time.monotonic()
            self._data[session_id] = conversation
            while len(self._data) > self.max_sessions:
                self._data.popitem(last=False)
