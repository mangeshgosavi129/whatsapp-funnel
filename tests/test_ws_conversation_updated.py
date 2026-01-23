#!/usr/bin/env python
import asyncio
import json
import os
import time
from typing import Any, Dict

import websockets
import requests

WS_URL = os.environ.get("WS_URL", "ws://127.0.0.1:8000/ws")
HTTP_BASE = os.environ.get("HTTP_BASE", "http://127.0.0.1:8000")
TOKEN = os.environ.get("WS_TOKEN")

async def wait_for_event(ws, event_name: str, timeout: float = 5.0) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict) and data.get("event") == event_name:
            return data
    raise TimeoutError(f"Did not receive event {event_name} within {timeout}s")

async def test_conversation_updated_contains_message() -> None:
    assert TOKEN, "Set WS_TOKEN env var with a valid JWT to run this test"

    url = f"{WS_URL}?token={TOKEN}"
    async with websockets.connect(url) as ws:
        # Trigger server to create a message and emit conversation:updated
        r = requests.post(f"{HTTP_BASE}/debug/message")
        assert r.status_code == 200, f"debug/message failed: {r.status_code} {r.text}"

        evt = await wait_for_event(ws, "conversation:updated", timeout=10.0)
        payload = evt.get("payload", {})
        assert "conversation" in payload, "payload.conversation missing"
        assert "message" in payload, "payload.message missing"
        msg = payload["message"]
        conv = payload["conversation"]
        assert msg.get("conversation_id") == conv.get("id"), "message.conversation_id should match conversation.id"

if __name__ == "__main__":
    asyncio.run(test_conversation_updated_contains_message())
