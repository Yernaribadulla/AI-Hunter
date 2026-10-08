from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
import sys
from typing import Optional


@dataclass
class PipelineEvent:
    type: str
    message: str
    timestamp: str = ""
    vacancy_id: Optional[str] = None
    vacancy_index: Optional[int] = None
    total: Optional[int] = None
    processed: Optional[int] = None
    apply: Optional[int] = None
    review: Optional[int] = None
    reject: Optional[int] = None
    score: Optional[int] = None
    decision: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")


def emit_event(event: PipelineEvent):
    if os.getenv("JOBHUNTER_GUI_EVENTS") != "1":
        return
    sys.stderr.write("__AIH_EVENT__" + json.dumps(asdict(event), ensure_ascii=False) + "\n")
    sys.stderr.flush()
