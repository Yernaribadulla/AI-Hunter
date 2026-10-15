"""Incremental UTF-8 event framing independent of Qt and pipe chunk sizes."""

import codecs
import json

EVENT_PREFIX = "__AIH_EVENT__"


class OutputDecoder:
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.buffer = ""

    def feed(self, data: bytes, final=False) -> list[tuple[str, object]]:
        self.buffer += self.decoder.decode(data, final=final)
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()
        if final and self.buffer:
            lines.append(self.buffer)
            self.buffer = ""
        result = []
        for line in lines:
            line = line.rstrip("\r")
            if line.startswith(EVENT_PREFIX):
                try:
                    event = json.loads(line[len(EVENT_PREFIX) :])
                    if not isinstance(event, dict):
                        raise ValueError("Event must be an object")
                    result.append(("event", event))
                except ValueError:
                    result.append(("text", "Некорректное событие pipeline: " + line))
            elif line.strip():
                result.append(("text", line))
        return result
