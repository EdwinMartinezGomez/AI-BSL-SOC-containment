# -*- coding: utf-8 -*-
"""AI-BSL platform — persistencia SQLite (stdlib).

Registra agentes, el ledger hash-chained (append-only) con su espejo externo
write-only, eventos, reviews y aprobaciones humanas. Sin dependencias externas.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'live',
  profile TEXT, policy_version TEXT, capability TEXT, ceiling TEXT,
  status TEXT DEFAULT 'active', active INTEGER DEFAULT 1, created_at TEXT,
  state_json TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
  agent_id TEXT NOT NULL, seq INTEGER NOT NULL, tick INTEGER, kind TEXT,
  payload TEXT, prev_hash TEXT, canon TEXT, hash TEXT,
  PRIMARY KEY (agent_id, seq)
);
CREATE TABLE IF NOT EXISTS ledger_ext (
  agent_id TEXT NOT NULL, seq INTEGER NOT NULL, tick INTEGER, kind TEXT,
  payload TEXT, hash TEXT, PRIMARY KEY (agent_id, seq)
);
CREATE TABLE IF NOT EXISTS events (
  agent_id TEXT, tick INTEGER, ts TEXT, kind TEXT, target TEXT, detail TEXT,
  dangerous INTEGER, blocked INTEGER, contained INTEGER, signal TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY, agent_id TEXT, tick INTEGER, tipo TEXT, causa TEXT,
  postura TEXT, status TEXT DEFAULT 'open', decision TEXT, note TEXT,
  by TEXT, decided_at TEXT, ledger_seq INTEGER
);
CREATE TABLE IF NOT EXISTS humans (
  agent_id TEXT, tick INTEGER, kind TEXT, decision TEXT, by TEXT, note TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS policies (
  version TEXT PRIMARY KEY, author TEXT, note TEXT, content TEXT, registered_at TEXT
);
"""


class Database:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path(__file__).parent.parent / "data" / "aibsl.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- agentes ----------
    def save_agent(self, agent: Dict[str, Any]):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO agents (id,name,mode,profile,policy_version,capability,"
                "ceiling,status,active,created_at,state_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (agent["id"], agent["name"], agent.get("mode", "live"), agent.get("profile"),
                 agent.get("policy_version"), json.dumps(agent["capability"], ensure_ascii=False),
                 agent.get("ceiling"), agent.get("status", "active"),
                 1 if agent.get("active", True) else 0, agent.get("created_at"),
                 json.dumps(agent.get("state_json", {}), ensure_ascii=False)))
            self.conn.commit()

    def agents(self) -> List[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM agents ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def get_agent_row(self, agent_id: str) -> Optional[dict]:
        with self._lock:
            r = self.conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        return dict(r) if r else None

    def update_agent_state(self, agent_id: str, status: str, active: int, state_json: dict):
        with self._lock:
            self.conn.execute(
                "UPDATE agents SET status=?, active=?, state_json=? WHERE id=?",
                (status, active, json.dumps(state_json, ensure_ascii=False), agent_id))
            self.conn.commit()

    # ---------- ledger ----------
    def append_ledger(self, agent_id: str, seq: int, tick: int, kind: str,
                      payload: dict, prev_hash: str, canon: str, hash_: str):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO ledger (agent_id,seq,tick,kind,payload,prev_hash,canon,hash) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (agent_id, seq, tick, kind, json.dumps(payload, ensure_ascii=False),
                 prev_hash, canon, hash_))
            self.conn.execute(
                "INSERT OR IGNORE INTO ledger_ext (agent_id,seq,tick,kind,payload,hash) VALUES (?,?,?,?,?,?)",
                (agent_id, seq, tick, kind, json.dumps(payload, ensure_ascii=False), hash_))
            self.conn.commit()

    def ledger_entries(self, agent_id: str) -> List[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT seq,tick,kind,payload,prev_hash,canon,hash FROM ledger WHERE agent_id=? ORDER BY seq",
                (agent_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            out.append({
                "seq": d["seq"], "tick": d["tick"], "kind": d["kind"],
                "payload": json.loads(d["payload"]), "prev_hash": d["prev_hash"],
                "canon": d["canon"], "hash": d["hash"]})
        return out

    # ---------- eventos / reviews / humanos ----------
    def append_event(self, agent_id: str, tick: int, ts: str, kind: str, target: Optional[str],
                     detail: dict, dangerous: bool, blocked: bool, contained: bool, signal: Optional[str]):
        with self._lock:
            self.conn.execute(
                "INSERT INTO events (agent_id,tick,ts,kind,target,detail,dangerous,blocked,contained,signal) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (agent_id, tick, ts, kind, target, json.dumps(detail, ensure_ascii=False),
                 int(dangerous), int(blocked), int(contained), signal))
            self.conn.commit()

    def events(self, agent_id: str, limit: int = 500) -> List[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE agent_id=? ORDER BY tick DESC, rowid DESC LIMIT ?",
                (agent_id, limit)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d["detail"] or "{}")
            d["dangerous"] = bool(d["dangerous"])
            d["blocked"] = bool(d["blocked"])
            d["contained"] = bool(d["contained"])
            out.append(d)
        return out

    def save_review(self, rv: Dict[str, Any]):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO reviews (review_id,agent_id,tick,tipo,causa,postura,status,"
                "decision,note,by,decided_at,ledger_seq) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (rv["review_id"], rv["agent_id"], rv["tick"], rv["tipo"], rv["causa"], rv["postura"],
                 rv.get("status", "open"), rv.get("decision"), rv.get("note"), rv.get("by"),
                 rv.get("decided_at"), rv.get("ledger_seq")))
            self.conn.commit()

    def updates_review(self, review_id: str, status: str, decision: str, note: str, by: str,
                       decided_at: str, ledger_seq: Optional[int]):
        with self._lock:
            self.conn.execute(
                "UPDATE reviews SET status=?,decision=?,note=?,by=?,decided_at=?,ledger_seq=? "
                "WHERE review_id=?",
                (status, decision, note, by, decided_at, ledger_seq, review_id))
            self.conn.commit()

    def reviews(self, agent_id: Optional[str] = None, status: Optional[str] = "open") -> List[dict]:
        with self._lock:
            if agent_id:
                rows = self.conn.execute(
                    "SELECT * FROM reviews WHERE agent_id=? AND status=? ORDER BY tick",
                    (agent_id, status or "%")).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM reviews WHERE status=? ORDER BY tick", (status or "%",)).fetchall()
        return [dict(r) for r in rows]

    def save_human(self, agent_id: str, tick: int, kind: str, decision: str, by: str, note: str, ts: str):
        with self._lock:
            self.conn.execute(
                "INSERT INTO humans (agent_id,tick,kind,decision,by,note,ts) VALUES (?,?,?,?,?,?,?)",
                (agent_id, tick, kind, decision, by, note, ts))
            self.conn.commit()

    # ---------- politica ----------
    def save_policy(self, version: str, content: str, author: str, note: str):
        import datetime
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO policies (version,author,note,content,registered_at) VALUES (?,?,?,?,?)",
                (version, author, note, content, datetime.datetime.now().isoformat()))
            self.conn.commit()

    def policy_meta(self) -> Dict[str, dict]:
        with self._lock:
            rows = self.conn.execute("SELECT version,author,note,registered_at FROM policies").fetchall()
        return {r["version"]: dict(r) for r in rows}

    def ledger_verify(self, agent_id: str) -> List[int]:
        """Devuelve lista de seqs con hash invalido; vacia => integra."""
        from .ledger_store import verify_entries
        entries = self.ledger_entries(agent_id)
        return verify_entries(entries)