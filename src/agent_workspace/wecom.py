"""Optional WeCom text bridge using WecomTeam's SDK. No implicit reply or business retry.

Run under the local bridge supervisor, not as an Agent or a Message Backend.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

from .util import Error, read_json


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


class QuietLogger:
    # Never write SDK payloads, secrets or protocol chatter into the supervisor's stdout.
    def debug(self, message, *args):
        pass
    def info(self, message, *args):
        pass
    def warn(self, message, *args):
        pass
    def error(self, message, *args):
        emit({"event": "error", "reason": "wecom_sdk_error"})


async def serve():
    try:
        from aibot import WSClient, WSClientOptions
    except ImportError:
        emit({"event": "error", "reason": "Install the wecom optional dependency.", "fatal": True})
        return 78
    root = Path(os.environ["AW_INSTANCE_ROOT"])
    name = os.environ["AW_BRIDGE_NAME"]
    config = read_json(root / ".aw-local/bridges" / f"{name}.json")
    bot_id = os.environ.get(config.get("bot_id_env", "WECOM_BOT_ID"))
    secret = os.environ.get(config.get("secret_env", "WECOM_BOT_SECRET"))
    allowed = set(config.get("allowed_chat_ids", []))
    if not bot_id or not secret or not allowed:
        emit({"event": "error", "reason": "Bot credentials and allowed_chat_ids are required.", "fatal": True})
        return 78
    closed = asyncio.Event()
    client = WSClient(WSClientOptions(bot_id=bot_id, secret=secret, logger=QuietLogger(), max_reconnect_attempts=0))

    @client.on("authenticated")
    def authenticated():
        emit({"event": "ready"})

    @client.on("disconnected")
    def disconnected(reason=""):
        emit({"event": "disconnected", "reason": "wecom_connection_closed"})
        closed.set()

    @client.on("error")
    def error(exc):
        emit({"event": "error", "reason": type(exc).__name__})
        closed.set()

    @client.on("message.text")
    async def message(frame):
        body = frame.get("body", {})
        sender = body.get("from", {}).get("userid", "")
        target = body.get("chatid") or sender
        identifier = body.get("msgid")
        text = body.get("text", {}).get("content")
        if target not in allowed or not identifier or not text:
            return
        emit({"event": "input", "id": identifier, "sender": sender, "target": target, "text": text})

    async def commands():
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                closed.set()
                return
            item = json.loads(line)
            if item.get("event") != "send":
                continue
            if item["target"] not in allowed:
                emit({"event": "send_unknown", "id": item["id"], "receipt": "target_not_allowed"})
                continue
            try:
                # Keep a single send one SDK operation; do not partially replay split replies.
                if len(item["text"].encode()) > 4000:
                    raise Error("Split the reply explicitly into smaller sends before requesting delivery.")
                result = await client.send_message(item["target"], {"msgtype": "markdown", "markdown": {"content": item["text"]}})
                if result.get("errcode") != 0:
                    raise Error("WeCom did not return a successful receipt.")
                emit({"event": "sent", "id": item["id"], "receipt": {"errcode": 0}})
            except Exception as exc:
                emit({"event": "send_unknown", "id": item["id"], "receipt": type(exc).__name__})
    task = None
    try:
        await client.connect()
        task = asyncio.create_task(commands())
        await closed.wait()
    finally:
        client.disconnect()
        if task:
            task.cancel()
    return 1


def main():
    try:
        return asyncio.run(serve())
    except (KeyError, ValueError, FileNotFoundError):
        emit({"event": "error", "reason": "invalid_bridge_environment", "fatal": True})
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
