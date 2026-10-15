"""History service: SQLite owns records and duplicate protection."""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from fastapi import FastAPI, Query
from pydantic import BaseModel

BLOCKED = {
    "applied",
    "already_applied",
    "rejected_by_ai",
    "submission_pending",
    "unknown",
    "send_error",
}


class Record(BaseModel):
    timestamp: str
    vacancy: dict
    result: dict


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS blocked (vacancy_id TEXT PRIMARY KEY)"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def append(self, record):
        payload = record.model_dump() if isinstance(record, Record) else record
        vacancy_id = str(payload["vacancy"].get("id", ""))
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT INTO records(payload) VALUES (?)",
                (json.dumps(payload, ensure_ascii=False),),
            )
            if vacancy_id and payload["result"].get("status") in BLOCKED:
                db.execute("INSERT OR IGNORE INTO blocked VALUES (?)", (vacancy_id,))

    def processed(self):
        with closing(self.connect()) as db:
            return [r[0] for r in db.execute("SELECT vacancy_id FROM blocked")]

    def records(self, limit=500, before=None):
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT id,payload FROM records WHERE id < ? ORDER BY id DESC LIMIT ?",
                (before if before is not None else 2**63 - 1, limit),
            ).fetchall()
        return [{"record_id": row[0], **json.loads(row[1])} for row in rows]


def create_app(path=None):
    app = FastAPI(title="AI-Hunter history", version="1.0")
    # Lazy initialization avoids filesystem writes merely by importing the module.
    store = None

    def get_store():
        nonlocal store
        if store is None:
            store = Store(
                path
                or os.getenv(
                    "JOBHUNTER_DB",
                    str(Path(__file__).resolve().parents[1] / "data/history.sqlite3"),
                )
            )
        return store

    @app.get("/health")
    def health():
        get_store()
        return {"status": "ok", "service": "history"}

    @app.get("/v1/processed")
    def processed():
        return {"ids": get_store().processed()}

    @app.post("/v1/records", status_code=201)
    def append(record: Record):
        get_store().append(record)
        return {"saved": True}

    @app.get("/v1/records")
    def records(
        limit: int = Query(500, ge=1, le=1000), before: int | None = Query(None, ge=1)
    ):
        return get_store().records(limit, before)

    return app


app = create_app()
