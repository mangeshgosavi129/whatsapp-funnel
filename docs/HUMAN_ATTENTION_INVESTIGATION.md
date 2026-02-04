# Human Attention & Takeover Investigation

> **Date**: 2025-02-05  
> **Status**: Investigation Complete

---

## System Overview

**Human Attention Flag** (`needs_human_attention`):
- Set by LLM when it detects need for human intervention (risk flags, confusion, explicit request)
- Triggers WebSocket event `ACTION_HUMAN_ATTENTION_REQUIRED` via toast notification
- Cleared manually via `PATCH /conversations/{id}` with `needs_human_attention: false`

**Takeover/Release** (`mode: BOT | HUMAN`):
- Two pathways: REST API (`/takeover`, `/release`) or WebSocket events
- When `mode=HUMAN`, worker skips LLM pipeline - just stores user message
- Human can send messages manually via frontend
- Release returns to `mode=BOT`

---

## 🔴 Issues Found

### Issue 1: `needs_human_attention` NOT Cleared on Takeover

**Location**: `conversations.py` (takeover endpoint, lines 97-114)

**Problem**:
```python
db_conv.mode = ConversationMode.HUMAN
# NOTE: needs_human_attention is NOT set to False here!
```

When a human takes over, the flag remains `True`. This means:
- Dashboard still shows conversation as "needing attention"
- Actionable count remains inflated
- Visual inconsistency

**Recommendation**:
```python
# In takeover_conversation():
db_conv.mode = ConversationMode.HUMAN
db_conv.needs_human_attention = False  # Clear the flag
db_conv.human_attention_resolved_at = datetime.utcnow()
```

---

### Issue 2: Duplicate Takeover Pathways (REST + WebSocket)

**Location**:
- REST: `conversations.py` → `/takeover`, `/release`
- WebSocket: `websocket_events.py` → `handle_takeover_started`, `handle_takeover_ended`

**Problem**:
- Two ways to do the same thing
- If frontend uses one, backend state could be out of sync with other clients
- REST endpoints don't broadcast WebSocket events
- WebSocket handlers don't use REST endpoints

**Current behavior**:
- REST: Updates DB only, no broadcast
- WebSocket: Updates DB + broadcasts `CONVERSATION_UPDATED`

**Recommendation**:
Option A: Remove REST endpoints, use WebSocket only  
Option B: REST endpoints should trigger same WebSocket broadcast

---

### Issue 3: No Notification to User When in HUMAN Mode

**Location**: `main.py` line 228-229

**Problem**:
```python
if conversation.get("mode") == ConversationMode.HUMAN.value:
    return {"status": "ok", "mode": "human"}, 200  # Silent return
```

When human takes over and user sends message:
- Message is stored
- No notification to the human that a new message arrived
- Human must manually refresh or rely on polling

**Recommendation**:
Emit WebSocket event `CONVERSATION_UPDATED` with new message even in HUMAN mode

---

### Issue 4: No Auto-Release Mechanism

**Problem**:
If human takes over and forgets to release:
- Conversation stays in HUMAN mode forever
- User messages never get bot responses
- No timeout or reminder

**Recommendation**:
Add auto-release after N minutes of inactivity (configurable), or at least a reminder/alert

---

### Issue 5: Race Condition on Mode Check

**Location**: `main.py` line 228

**Problem**:
```python
conversation = api_client.get_conversation(conversation_id)
# ... time passes ...
if conversation.get("mode") == ConversationMode.HUMAN.value:
```

Mode could change between fetch and check. Low probability but possible.

**Recommendation**:
Use optimistic locking or check mode again before critical operations

---

### Issue 6: Frontend Bot Mode Blocks Input

**Location**: `ChatViewer.jsx` line 100-101

**Problem**:
```jsx
disabled={conversation?.mode === 'bot'}
placeholder="Bot is active. Takeover to chat."
```

When bot is active, human cannot type at all. This is by design, but:
- No way to send "urgent override" message
- Human must takeover first, then type

**Recommendation** (optional):
Allow typing but show confirmation: "This will takeover from bot. Continue?"

---

## Summary Table

| Issue | Severity | Effort | Recommended Action |
|-------|----------|--------|-------------------|
| 1. Flag not cleared on takeover | **High** | Low | Add 2 lines to takeover endpoint |
| 2. Duplicate REST/WS pathways | Medium | Medium | Consolidate or sync broadcasts |
| 3. No WS event in HUMAN mode | Medium | Low | Emit event after storing message |
| 4. No auto-release timeout | Medium | Medium | Add scheduled check or reminder |
| 5. Race condition on mode | Low | Low | Add optimistic lock |
| 6. Input blocked in bot mode | Low | Low | Optional UX improvement |

---

## Quick Fixes (Low Effort)

**Issue 1 Fix** (Most Important):
```python
# In takeover_conversation() - conversations.py
from datetime import datetime

db_conv.mode = ConversationMode.HUMAN
db_conv.needs_human_attention = False
db_conv.human_attention_resolved_at = datetime.utcnow()
```
