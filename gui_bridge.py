import json
import os
import socket


def request(payload):
    port = int(os.environ["JOBHUNTER_GUI_BRIDGE_PORT"])
    with socket.create_connection(("127.0.0.1", port), timeout=None) as connection:
        connection.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        data = b""
        while not data.endswith(b"\n"):
            chunk = connection.recv(4096)
            if not chunk:
                raise RuntimeError("GUI bridge closed before sending a response")
            data += chunk
    return json.loads(data.decode("utf-8"))
