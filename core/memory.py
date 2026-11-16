"""
Conversational Memory Module for J.A.R.V.I.S. Desktop Assistant.
Combines:
1. Short-Term Sliding-Window Working Memory (Session Chat Context).
2. Long-Term Relational Memory (SQLite for preferences and task logs).
3. Long-Term Semantic Vector Memory (ChromaDB for associative knowledge recall).
"""

from __future__ import annotations
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import config

logger = logging.getLogger("JARVIS.Memory")


class ShortTermMemory:
    """Sliding-window working memory for the ongoing conversational session."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self.messages: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Append a message turn to context."""
        msg = {"role": role, "content": content}
        msg.update(kwargs)
        self.messages.append(msg)
        # Keep within max turn window while preserving system prompt if first
        if len(self.messages) > self.max_turns:
            if self.messages[0].get("role") == "system":
                self.messages = [self.messages[0]] + self.messages[-(self.max_turns - 1):]
            else:
                self.messages = self.messages[-self.max_turns:]

    def get_messages(self) -> List[Dict[str, Any]]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()


class LongTermRelationalMemory:
    """SQLite-backed persistent store for preferences, facts, and task history."""

    def __init__(self, db_path: Path = config.storage.sqlite_db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create tables for key-value preferences and task execution records."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Preferences & User Profile
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    pref_key TEXT PRIMARY KEY,
                    pref_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            # Historical Task Log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_summary TEXT NOT NULL,
                    tool_used TEXT,
                    status TEXT NOT NULL,
                    result_summary TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            # Semantic Knowledge Notes Fallback Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    note_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def set_preference(self, key: str, value: Any) -> None:
        """Store or update user preference."""
        val_str = json.dumps(value) if not isinstance(value, str) else value
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_preferences (pref_key, pref_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(pref_key) DO UPDATE SET
                    pref_value=excluded.pref_value,
                    updated_at=excluded.updated_at
            """, (key, val_str, now))
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored preference."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT pref_value FROM user_preferences WHERE pref_key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return row[0]
            return default

    def log_task(self, summary: str, tool_used: str, status: str, result: str) -> None:
        """Record an executed task in persistent log."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_log (task_summary, tool_used, status, result_summary, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (summary, tool_used, status, result[:500], now))
            conn.commit()

    def store_note(self, category: str, note_text: str) -> None:
        """Store knowledge note for fallback recall."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge_notes (category, note_text, created_at)
                VALUES (?, ?, ?)
            """, (category, note_text, now))
            conn.commit()

    def search_notes(self, query: str, limit: int = 5) -> List[str]:
        """Keyword matching fallback for notes across words in query."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Split query into words to find partial matches
            words = [w.strip() for w in query.split() if len(w.strip()) > 2]
            if not words:
                words = [query]

            conditions = []
            params = []
            for w in words:
                conditions.append("(note_text LIKE ? OR category LIKE ?)")
                wildcard = f"%{w}%"
                params.extend([wildcard, wildcard])

            where_clause = " OR ".join(conditions)
            sql = f"""
                SELECT category, note_text FROM knowledge_notes
                WHERE {where_clause}
                ORDER BY id DESC LIMIT ?
            """
            params.append(limit)
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return [f"[{cat}] {text}" for cat, text in rows]


class SemanticVectorMemory:
    """ChromaDB-powered semantic vector memory for similarity search and knowledge retrieval."""

    def __init__(self, persist_dir: Path = config.storage.chroma_dir):
        self.persist_dir = persist_dir
        self.collection = None
        self._initialize_chroma()

    def _initialize_chroma(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings
            client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = client.get_or_create_collection(
                name="jarvis_long_term_memory",
                metadata={"description": "Stores user knowledge, instructions, and past memories"}
            )
            logger.info("ChromaDB vector memory initialized successfully.")
        except Exception as e:
            logger.warning(f"ChromaDB not available or failed to initialize ({e}). Falling back to SQLite memory.")
            self.collection = None

    def store_memory(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Embed and store a memory snippet."""
        if not self.collection:
            return False
        try:
            meta = metadata or {}
            meta["timestamp"] = datetime.now().isoformat()
            self.collection.upsert(
                documents=[text],
                ids=[doc_id],
                metadatas=[meta]
            )
            return True
        except Exception as e:
            logger.error(f"Error upserting memory into ChromaDB: {e}")
            return False

    def query_memories(self, query_text: str, top_k: int = 3) -> List[str]:
        """Semantic search for memories most relevant to query_text."""
        if not self.collection:
            return []
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k
            )
            docs = results.get("documents", [[]])[0]
            return docs
        except Exception as e:
            logger.error(f"Error querying ChromaDB vector store: {e}")
            return []


class MemoryManager:
    """Unified Memory Facade coordinating Short-Term, SQLite, and ChromaDB."""

    def __init__(self):
        self.short_term = ShortTermMemory(max_turns=24)
        self.relational = LongTermRelationalMemory()
        self.vector = SemanticVectorMemory()

    def add_user_turn(self, text: str) -> None:
        self.short_term.add_message("user", text)

    def add_assistant_turn(self, text: str, tool_calls: Optional[List[Dict[str, Any]]] = None) -> None:
        kwargs = {}
        if tool_calls:
            kwargs["tool_calls"] = tool_calls
        self.short_term.add_message("assistant", text, **kwargs)

    def add_tool_turn(self, tool_call_id: str, tool_name: str, result_content: str) -> None:
        self.short_term.add_message(
            role="tool",
            content=result_content,
            name=tool_name,
            tool_call_id=tool_call_id
        )

    def remember_knowledge(self, text: str, category: str = "general") -> None:
        """Stores a fact in both SQLite and semantic vector store."""
        doc_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.relational.store_note(category, text)
        self.vector.store_memory(doc_id, text, {"category": category})

    def recall_relevant_context(self, current_query: str) -> str:
        """Retrieves semantically relevant long-term memories and user preferences."""
        recalled_snippets = []

        # Vector search
        vector_results = self.vector.query_memories(current_query, top_k=3)
        if vector_results:
            recalled_snippets.extend(vector_results)
        else:
            # Fallback to relational keyword search
            kw_results = self.relational.search_notes(current_query, limit=3)
            recalled_snippets.extend(kw_results)

        if not recalled_snippets:
            return ""

        context_str = "--- [Long-Term Memory Recall] ---\n"
        for i, snippet in enumerate(recalled_snippets, 1):
            context_str += f"{i}. {snippet}\n"
        return context_str


# Global Memory Manager Singleton
memory = MemoryManager()
