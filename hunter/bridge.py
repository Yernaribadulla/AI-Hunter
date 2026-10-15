"""Loopback request bridge. Pending requests always resolve on shutdown."""

import json
import queue
import socketserver
import threading

MAX_MESSAGE = 128 * 1024


class PendingRequest:
    def __init__(self, payload):
        self.payload = payload
        self.event = threading.Event()
        self.response = {"action": "skip"}
        self.lock = threading.Lock()

    def resolve(self, response):
        # A late dialog click must never override cancellation during stop.
        with self.lock:
            if not self.event.is_set():
                self.response = response
                self.event.set()


class BridgeHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE or not raw.endswith(b"\n"):
                raise ValueError("Invalid bridge frame")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("Invalid bridge payload")
            request = PendingRequest(payload)
            with self.server.lock:
                if self.server.closing.is_set():
                    return
                self.server.pending.add(request)
            try:
                self.server.requests.put(request)
                request.event.wait()
                self.wfile.write(
                    (json.dumps(request.response, ensure_ascii=False) + "\n").encode(
                        "utf-8"
                    )
                )
            finally:
                with self.server.lock:
                    self.server.pending.discard(request)
        except (ValueError, OSError):
            try:
                self.wfile.write(b'{"action":"skip"}\n')
            except OSError:
                pass


class BridgeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        self.requests = queue.Queue()
        self.pending = set()
        self.lock = threading.Lock()
        self.closing = threading.Event()
        super().__init__(("127.0.0.1", 0), BridgeHandler)
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def cancel_pending(self):
        with self.lock:
            for request in self.pending:
                request.resolve({"action": "skip"})

    def close(self):
        self.closing.set()
        self.cancel_pending()
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)
