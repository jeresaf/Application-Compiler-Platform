"""Experimental versioned JSON worker guard; no authority or compiler state."""
import json
import subprocess
import os
import selectors
import signal
import tempfile
import time

MAX_MESSAGE = 1048576


class WorkerFailure(Exception):
    pass


def exchange(command, payload, *, timeout=1, cancelled=None):
    if cancelled is not None and cancelled.is_set():
        raise WorkerFailure("CANCELLED")
    request = json.dumps({"protocol": "acp-experiment/1", "payload": payload}).encode()
    if len(request) > MAX_MESSAGE:
        raise WorkerFailure("REQUEST_SIZE")
    with tempfile.TemporaryFile() as source:
        source.write(request)
        source.seek(0)
        process = subprocess.Popen(command, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    with process, selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        chunks = []
        size = 0
        deadline = time.monotonic() + timeout
        try:
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise WorkerFailure("CANCELLED")
                if time.monotonic() >= deadline:
                    raise WorkerFailure("TIMEOUT")
                if not selector.select(.02):
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_MESSAGE:
                    raise WorkerFailure("RESPONSE_SIZE")
                chunks.append(chunk)
            process.wait(timeout=max(.001, deadline-time.monotonic()))
        except (WorkerFailure, subprocess.TimeoutExpired) as error:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            if isinstance(error, subprocess.TimeoutExpired):
                raise WorkerFailure("TIMEOUT") from None
            raise
        output = b"".join(chunks)
        if process.returncode:
            raise WorkerFailure("CRASH")
        if len(output) > MAX_MESSAGE:
            raise WorkerFailure("RESPONSE_SIZE")
        try:
            response = json.loads(output)
        except (ValueError, UnicodeError):
            raise WorkerFailure("MALFORMED") from None
        if not isinstance(response, dict) or response.get("protocol") != "acp-experiment/1":
            raise WorkerFailure("VERSION")
        return response


if __name__ == "__main__":
    import sys
    request = json.load(sys.stdin)
    json.dump({"protocol": "acp-experiment/1", "payload": request["payload"]}, sys.stdout)
