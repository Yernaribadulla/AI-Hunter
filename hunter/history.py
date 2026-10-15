"""Append-only JSONL storage shared by the pipeline and desktop."""

import json
from pathlib import Path

FINAL_STATUSES = frozenset({"applied", "already_applied", "rejected_by_ai"})


class HistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def records(self) -> list[dict]:
        records = []
        if not self.path.exists():
            return records
        with self.path.open(encoding="utf-8-sig", errors="replace") as source:
            for line in source:
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeError):
                    continue  # A partial final line can be written by the worker.
                if (
                    isinstance(record, dict)
                    and isinstance(record.get("vacancy"), dict)
                    and isinstance(record.get("result"), dict)
                ):
                    records.append(record)
        return records

    def processed_ids(self) -> set[str]:
        return {
            str(row["vacancy"]["id"])
            for row in self.records()
            if row["vacancy"].get("id") is not None
            and row["result"].get("status") in FINAL_STATUSES
        }

    def append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as target:
            target.write(json.dumps(record, ensure_ascii=False) + "\n")


def display_name(value) -> str:
    return str(value.get("name", "")) if isinstance(value, dict) else str(value or "")


def vacancy_values(record: dict) -> list:
    vacancy, result = record["vacancy"], record["result"]
    return [
        vacancy.get("title") or vacancy.get("name") or "Без названия",
        display_name(vacancy.get("company") or vacancy.get("employer")),
        result.get("score"),
        "Удалённо" if result.get("is_remote") else "Не указано / офис",
        str(result.get("decision", "—")).upper(),
        result.get("status", "—"),
    ]
