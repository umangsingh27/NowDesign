"""
Session event bus — thread-safe per-session SSE queue and DIALOGUE-state signalling.

Two responsibilities:
  1. SSEEvent queue: pipeline threads push progress/error/complete events;
     the API route drains the queue and streams them to the browser.
  2. Dialogue gate: AskClarification puts the pipeline thread to sleep by waiting
     on a threading.Event; the /api/session/answer endpoint unblocks it by calling
     resolve_dialogue() with the user's answers.

One EventBusRegistry is shared by the whole process. One SessionEventBus per active
session. Buses are created at session start and removed at APPROVED or on error.
"""

import threading
import queue
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SSEEvent:
    """A single server-sent event pushed from the pipeline to the browser."""
    event: str          # "progress" | "dialogue" | "error" | "complete"
    data: dict
    sent_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionEventBus:
    """
    Per-session event channel. Created once at session start; lives until APPROVED.

    Thread-safety contract:
      - emit() is safe to call from any thread.
      - wait_for_dialogue_answers() BLOCKS the calling (pipeline) thread until
        resolve_dialogue() is called from a separate (API handler) thread.
      - All state mutations are protected by _lock.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.sse_queue: queue.Queue[SSEEvent] = queue.Queue()
        self._dialogue_event = threading.Event()
        self._dialogue_answers: list[str] = []
        self._lock = threading.Lock()

    # ── SSE event channel ─────────────────────────────────────────────────

    def emit(self, event: str, data: dict) -> None:
        """Push an SSE event. Safe to call from any thread."""
        self.sse_queue.put(SSEEvent(event=event, data=data))

    def drain(self) -> list[SSEEvent]:
        """Non-blocking drain of all queued events. Used by the SSE API route."""
        events: list[SSEEvent] = []
        while True:
            try:
                events.append(self.sse_queue.get_nowait())
            except queue.Empty:
                break
        return events

    # ── Dialogue gate ──────────────────────────────────────────────────────

    def wait_for_dialogue_answers(self, timeout: float = 600.0) -> list[str]:
        """
        Block the pipeline thread until the user submits answers.
        Returns the list of answer strings.
        Raises TimeoutError if the user doesn't respond within `timeout` seconds.
        """
        answered = self._dialogue_event.wait(timeout=timeout)
        if not answered:
            raise TimeoutError(
                f"Session {self.session_id}: user did not answer "
                f"clarification questions within {timeout}s"
            )
        with self._lock:
            self._dialogue_event.clear()
            return list(self._dialogue_answers)

    def resolve_dialogue(self, answers: list[str]) -> None:
        """
        Called by the API answer endpoint when the user submits answers.
        Unblocks the pipeline thread that is waiting in wait_for_dialogue_answers().
        """
        with self._lock:
            self._dialogue_answers = list(answers)
        self._dialogue_event.set()

    def is_dialogue_pending(self) -> bool:
        """True if the pipeline is currently blocked waiting for user answers."""
        return not self._dialogue_event.is_set() and bool(self._dialogue_answers) is False

    # ── Convenience progress emitter ──────────────────────────────────────

    def progress(self, message: str, step: Optional[int] = None, total: Optional[int] = None) -> None:
        """Emit a progress event. Shorthand used throughout the pipeline."""
        data: dict = {"message": message}
        if step is not None:
            data["step"] = step
        if total is not None:
            data["total"] = total
        self.emit("progress", data)


class EventBusRegistry:
    """
    Process-wide registry of active session buses.
    All methods are class-methods — no instance needed.
    Thread-safe via a module-level lock.
    """

    _buses: dict[str, SessionEventBus] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def create(cls, session_id: str) -> SessionEventBus:
        """Create and register a new bus. Overwrites any existing bus for the same id."""
        bus = SessionEventBus(session_id)
        with cls._lock:
            cls._buses[session_id] = bus
        return bus

    @classmethod
    def get(cls, session_id: str) -> Optional[SessionEventBus]:
        """Return the bus for session_id, or None if not found."""
        return cls._buses.get(session_id)

    @classmethod
    def get_or_create(cls, session_id: str) -> SessionEventBus:
        """Return existing bus or create a new one."""
        with cls._lock:
            if session_id not in cls._buses:
                cls._buses[session_id] = SessionEventBus(session_id)
            return cls._buses[session_id]

    @classmethod
    def remove(cls, session_id: str) -> None:
        """Remove the bus when the session ends."""
        with cls._lock:
            cls._buses.pop(session_id, None)

    @classmethod
    def active_count(cls) -> int:
        """Number of currently active session buses."""
        return len(cls._buses)


# ── Module-level convenience functions ────────────────────────────────────────

def set_dialogue_questions(session_id: str, questions: list[str]) -> None:
    """
    Emit a dialogue SSE event on the session's event bus.
    Called by AskClarification skill and the pipeline orchestrator.
    No-ops gracefully if no bus exists for the session.
    """
    bus = EventBusRegistry.get(session_id)
    if bus is not None:
        bus.emit("dialogue", {
            "questions": questions,
            "count": len(questions),
            "session_id": session_id
        })


def resolve_dialogue_answers(session_id: str, answers: list[str]) -> None:
    """
    Unblock a pipeline waiting for dialogue answers.
    Called by the /api/session/answer API endpoint.
    Raises KeyError if no bus exists for the session.
    """
    bus = EventBusRegistry.get(session_id)
    if bus is None:
        raise KeyError(f"No active event bus for session '{session_id}'")
    bus.resolve_dialogue(answers)


if __name__ == "__main__":
    import time

    print("Testing SessionEventBus...")

    bus = EventBusRegistry.create("sess_test_events")

    # Test 1: emit and drain
    bus.emit("progress", {"message": "Querying brand knowledge..."})
    bus.progress("Planning layout...", step=2, total=6)
    events = bus.drain()
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"
    assert events[0].event == "progress"
    assert events[1].data["step"] == 2
    print("  emit + drain: OK")

    # Test 2: empty drain returns []
    assert bus.drain() == []
    print("  empty drain: OK")

    # Test 3: dialogue gate — thread-based round-trip
    answers_received: list[list] = []

    def pipeline_thread():
        answers = bus.wait_for_dialogue_answers(timeout=5.0)
        answers_received.append(answers)

    def api_thread():
        time.sleep(0.05)  # simulate brief delay
        bus.resolve_dialogue(["ductile iron castings", "premium automotive sector"])

    t1 = threading.Thread(target=pipeline_thread, daemon=True)
    t2 = threading.Thread(target=api_thread, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=6.0)
    t2.join(timeout=6.0)

    assert len(answers_received) == 1, "Pipeline thread did not receive answers"
    assert answers_received[0] == ["ductile iron castings", "premium automotive sector"]
    print("  dialogue gate (cross-thread signal): OK")

    # Test 4: registry
    assert EventBusRegistry.get("sess_test_events") is bus
    assert EventBusRegistry.active_count() == 1
    EventBusRegistry.remove("sess_test_events")
    assert EventBusRegistry.get("sess_test_events") is None
    print("  registry create/get/remove: OK")

    print("session_events: ALL TESTS PASSED")
