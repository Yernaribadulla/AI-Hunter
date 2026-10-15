"""Explicitly import old JSONL history through the history API."""

import argparse
import json
from pathlib import Path
import requests
from services.client import HISTORY_URL
from services.history import Record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    # Validate the entire input before making any changes.
    records = [
        Record.model_validate(json.loads(line))
        for line in args.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record in records:
        response = requests.post(
            HISTORY_URL + "/v1/records", json=record.model_dump(), timeout=10
        )
        response.raise_for_status()
    print(f"Imported {len(records)} records. Original file preserved.")


if __name__ == "__main__":
    main()
