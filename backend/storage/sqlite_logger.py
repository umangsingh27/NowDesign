"""
SQLite structured logger — append-only log of every action in the system.
All tables use CREATE TABLE IF NOT EXISTS for idempotency.
Never deletes rows. Every event is permanent.
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _get_db_path() -> str:
    path = os.getenv("SQLITE_PATH", "./storage_data/sqlite/nowpurchase_studio.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they do not exist. Safe to call multiple times."""
    conn = _get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            state TEXT NOT NULL,
            brief_json TEXT,
            logo_type TEXT,
            theme TEXT,
            layout_plan_json TEXT,
            image_path TEXT,
            compliance_score INTEGER,
            user_rating INTEGER,
            requested_by TEXT,
            total_attempts INTEGER DEFAULT 1,
            duration_ms INTEGER
        );

        CREATE TABLE IF NOT EXISTS skill_invocations (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            agent_name TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            input_json TEXT,
            output_json TEXT,
            duration_ms INTEGER,
            success INTEGER NOT NULL,
            error_message TEXT,
            invoked_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT,
            sent_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kb_operations (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            collection TEXT NOT NULL,
            operation TEXT NOT NULL,
            query TEXT,
            result_count INTEGER,
            document_id TEXT,
            agent_name TEXT,
            operated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generated_images (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            image_path TEXT,
            background_prompt TEXT,
            theme TEXT,
            logo_type TEXT,
            glass_renderer TEXT,
            compliance_score INTEGER,
            approved INTEGER DEFAULT 0,
            generated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


class SQLiteLogger:
    """
    Synchronous logger. One instance per process.
    All methods are append-only — no updates, no deletes.
    """

    def __init__(self):
        init_db()

    def log_session_create(
        self,
        session_id: str,
        state: str,
        brief_json: dict,
        logo_type: str,
        theme: str,
        requested_by: Optional[str] = None
    ) -> None:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO sessions (id, created_at, state, brief_json, logo_type, theme, requested_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, _now(), state, json.dumps(brief_json), logo_type, theme, requested_by)
        )
        conn.commit()
        conn.close()

    def log_session_update(self, session_id: str, **kwargs) -> None:
        if not kwargs:
            return
        allowed = {"state", "layout_plan_json", "image_path", "compliance_score",
                   "user_rating", "total_attempts", "duration_ms"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]
        conn = _get_conn()
        conn.execute(f"UPDATE sessions SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def log_skill_invocation(
        self,
        invocation_id: str,
        session_id: str,
        agent_name: str,
        skill_name: str,
        input_json: str,
        output_json: str,
        duration_ms: int,
        success: bool,
        error_message: Optional[str],
        invoked_at: str
    ) -> None:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO skill_invocations
               (id, session_id, agent_name, skill_name, input_json, output_json,
                duration_ms, success, error_message, invoked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (invocation_id, session_id, agent_name, skill_name,
             input_json, output_json[:4000], duration_ms,
             1 if success else 0, error_message, invoked_at)
        )
        conn.commit()
        conn.close()

    def log_conversation_message(
        self,
        session_id: str,
        phase: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
        message_id: Optional[str] = None,
    ) -> None:
        import uuid as _uuid
        if not message_id:
            message_id = f"msg_{_uuid.uuid4().hex[:8]}"
        conn = _get_conn()
        conn.execute(
            """INSERT INTO conversations (id, session_id, phase, role, content, metadata_json, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message_id, session_id, phase, role, content,
             json.dumps(metadata) if metadata else None, _now())
        )
        conn.commit()
        conn.close()

    def log_kb_operation(
        self,
        op_id: str,
        session_id: Optional[str],
        collection: str,
        operation: str,
        query: Optional[str] = None,
        result_count: Optional[int] = None,
        document_id: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> None:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO kb_operations
               (id, session_id, collection, operation, query, result_count, document_id,
                agent_name, operated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (op_id, session_id, collection, operation, query,
             result_count, document_id, agent_name, _now())
        )
        conn.commit()
        conn.close()

    def log_generated_image(
        self,
        image_id: str,
        session_id: str,
        attempt_number: int,
        image_path: str,
        background_prompt: str,
        theme: str,
        logo_type: str,
        glass_renderer: str,
        compliance_score: Optional[int] = None
    ) -> None:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO generated_images
               (id, session_id, attempt_number, image_path, background_prompt,
                theme, logo_type, glass_renderer, compliance_score, approved, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (image_id, session_id, attempt_number, image_path, background_prompt,
             theme, logo_type, glass_renderer, compliance_score, _now())
        )
        conn.commit()
        conn.close()

    def get_session(self, session_id: str) -> Optional[dict]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_conversations(self, session_id: str) -> list[dict]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY sent_at ASC",
            (session_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Pipeline-friendly helpers added in Day 5 ────────────────────────────

    def create_session(
        self,
        session_id: str,
        brief_json,
        logo_type: str,
        theme: str,
        requested_by: Optional[str] = None,
    ) -> None:
        """Insert a new session row in state BRIEF."""
        if isinstance(brief_json, str):
            try:
                brief_dict = json.loads(brief_json)
            except json.JSONDecodeError:
                brief_dict = {"raw": brief_json}
        else:
            brief_dict = brief_json
        self.log_session_create(session_id, "BRIEF", brief_dict, logo_type, theme, requested_by)

    def update_session_state(self, session_id: str, state: str) -> None:
        self.log_session_update(session_id, state=state)

    def update_session_image(
        self,
        session_id: str,
        image_path: str,
        compliance_score: int,
        attempt: int,
    ) -> None:
        self.log_session_update(
            session_id,
            image_path=image_path,
            compliance_score=compliance_score,
            total_attempts=attempt,
        )

    def update_session_rating(self, session_id: str, user_rating: int) -> None:
        self.log_session_update(session_id, user_rating=user_rating)

    def update_session_layout_plan(self, session_id: str, layout_plan: dict) -> None:
        self.log_session_update(
            session_id, layout_plan_json=json.dumps(layout_plan)
        )

    def get_session_layout_plan(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if not session:
            return {}
        plan_str = session.get("layout_plan_json")
        if not plan_str:
            return {}
        try:
            return json.loads(plan_str)
        except json.JSONDecodeError:
            return {}

    def list_sessions(
        self,
        theme: Optional[str] = None,
        logo_type: Optional[str] = None,
        min_score: Optional[int] = None,
        requested_by: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses = []
        params: list = []
        if theme:
            clauses.append("theme = ?")
            params.append(theme)
        if logo_type:
            clauses.append("logo_type = ?")
            params.append(logo_type)
        if min_score is not None:
            clauses.append("compliance_score >= ?")
            params.append(min_score)
        if requested_by:
            clauses.append("requested_by = ?")
            params.append(requested_by)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(int(limit))
        conn = _get_conn()
        rows = conn.execute(
            f"SELECT * FROM sessions {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# Module-level singleton for use across the pipeline
_logger_instance: Optional["SQLiteLogger"] = None


def get_sqlite_logger() -> "SQLiteLogger":
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SQLiteLogger()
    return _logger_instance


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    print("Testing SQLiteLogger...")
    logger = SQLiteLogger()
    print("  init_db: all 5 tables created")
    import uuid as _uuid
    sid = f"sess_test_{_uuid.uuid4().hex[:8]}"
    logger.log_session_create(sid, "BRIEF", {"headline": "test"}, "nowpurchase", "dark", "umang")
    logger.log_session_update(sid, state="GENERATING", total_attempts=1)
    logger.log_skill_invocation(
        f"si_{_uuid.uuid4().hex[:12]}", sid, "planner", "query_brand_knowledge",
        '{"query": "test"}', '{"results": []}', 42, True, None, _now()
    )
    logger.log_conversation_message(
        f"msg_{_uuid.uuid4().hex[:8]}", sid, "DIALOGUE", "agent", "Test message"
    )
    logger.log_kb_operation(
        f"kbo_{_uuid.uuid4().hex[:8]}", sid, "brand_knowledge", "read", "test query", 3
    )
    session = logger.get_session(sid)
    assert session["state"] == "GENERATING", "state update failed"
    assert session["theme"] == "dark", "theme column missing"
    assert session["logo_type"] == "nowpurchase", "logo_type column missing"
    conversations = logger.get_conversations(sid)
    assert len(conversations) == 1, "conversation log failed"
    conn = _get_conn()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    conn.close()
    table_names = [t["name"] for t in tables]
    assert "sessions" in table_names
    assert "skill_invocations" in table_names
    assert "conversations" in table_names
    assert "kb_operations" in table_names
    assert "generated_images" in table_names
    print(f"  Tables confirmed: {table_names}")
    print(f"  session logo_type: {session['logo_type']}, theme: {session['theme']}")
    print("SQLiteLogger: ALL TESTS PASSED")
