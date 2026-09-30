"""Newline JSON-RPC client shared by actual stdio adapters, not an Agent loop."""
from __future__ import annotations

import json
import queue
import subprocess
import threading

from .util import Error, Unavailable, child_command


class Rpc:
    def __init__(self, command, *, cwd, env=None, on_event=None, on_request=None, jsonrpc=False):
        self.process = subprocess.Popen(child_command(command), cwd=cwd, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self.jsonrpc = jsonrpc
        self.pending = {}
        self.lock = threading.Lock()
        self.next_id = 1
        self.on_event = on_event
        self.on_request = on_request
        self.failure = None
        self.stderr_tail = ""
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        threading.Thread(target=self._stderr, daemon=True).start()

    def _stderr(self):
        for line in self.process.stderr:
            self.stderr_tail = (self.stderr_tail + line)[-4000:]

    def _read(self):
        try:
            for line in self.process.stdout:
                value = json.loads(line)
                if "method" in value and "id" in value:
                    threading.Thread(target=self._respond, args=(value,), daemon=True).start()
                elif "id" in value:
                    with self.lock:
                        target = self.pending.get(value["id"])
                    if target is not None:
                        target.put(value)
                elif self.on_event:
                    self.on_event(value)
        except Exception as exc:
            self.failure = f"RPC reader failed: {type(exc).__name__}"
        finally:
            self.failure = self.failure or "RPC connection closed"
            with self.lock:
                for target in self.pending.values():
                    target.put({"error": {"message": self.failure}})

    def _respond(self, request):
        try:
            if self.on_request is None:
                raise Error("No handler for this native server request.")
            result = self.on_request(request)
            self.send({"id": request["id"], "result": result})
        except Exception as exc:
            self.send({"id": request["id"], "error": {"code": -32603, "message": str(exc)}})

    def send(self, value):
        if self.jsonrpc:
            value = {"jsonrpc": "2.0", **value}
        with self.lock:
            self.process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
            self.process.stdin.flush()

    def request(self, method, params=None, timeout=30):
        target = queue.Queue()
        with self.lock:
            if self.failure:
                raise Unavailable(self.failure)
            identifier = self.next_id
            self.next_id += 1
            self.pending[identifier] = target
        try:
            self.send({"id": identifier, "method": method, "params": params or {}})
            try:
                value = target.get(timeout=timeout)
            except queue.Empty:
                raise Unavailable(f"RPC timeout for {method}; a write may already have happened.") from None
            if "error" in value:
                raise Unavailable(str(value["error"]))
            return value["result"]
        finally:
            with self.lock:
                self.pending.pop(identifier, None)

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        self.reader.join(timeout=2)
