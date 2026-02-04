# Followup System Investigation

> **Date**: 2025-02-05  
> **Status**: Investigation Complete

---

## System Overview

The followup system sends automated nudge messages when leads don't reply.

**Components:**
1. **Celery Beat** (`tasks.py`) - Runs `process_due_followups` every 60s
2. **API Endpoint** (`/internals/conversations/due-followups`) - Queries due conversations
3. **Pipeline** (`run_followup_pipeline`) - Generates followup message using LLM
4. **Buckets** - Time windows for each followup stage

**Followup Buckets:**
| Stage | Min Elapsed | Max Elapsed | Required Count |
|-------|-------------|-------------|----------------|
| FOLLOWUP_10M | 10 min | 20 min | 0 |
| FOLLOWUP_3H | 180 min | 200 min | 1 |
| FOLLOWUP_6H | 360 min | 400 min | 2 |

---

## 🔴 Issues Found

### Issue 1: `Followup` Model is Unused (Dead Code)

**Location**: `server/models.py` lines 166-179

```python
class Followup(Base):
    __tablename__ = "followups"
    id = ...
    template_id = ...  # Links to templates
    delay_hours = ...
    sequence_order = ...
```

**Problem**: This model exists but is NEVER queried or used anywhere. The actual followup logic uses hardcoded bucket timings in `internals.py`.

**Impact**: Dead code, misleading architecture

**Recommendation**: Either remove the model OR implement template-based followups using it.

---

### Issue 2: `scheduled_followup_at` Field is Unused

**Location**: `Conversation.scheduled_followup_at` column exists in models.py

**Problem**: The field is defined but never written to or queried. The due-followups query uses `last_bot_message_at` instead.

**Impact**: Unnecessary column, confusing schema

**Recommendation**: Remove the column if not needed, or use it for explicit scheduling.

---

### Issue 3: Plain `FOLLOWUP` Stage Not Mapped to Any Bucket

**Location**: `server/enums.py`

```python
class ConversationStage(str, Enum):
    FOLLOWUP = "followup"        # <-- Never used in buckets!
    FOLLOWUP_10M = "followup_10m"
    FOLLOWUP_3H = "followup_3h"
    FOLLOWUP_6H = "followup_6h"
```

**Problem**: `FOLLOWUP` stage exists but has no bucket mapping. A conversation set to `stage=FOLLOWUP` won't receive any automated messages.

**Impact**: Potential dead end if code ever sets this stage

**Recommendation**: Either remove `FOLLOWUP` or create a bucket for it.

---

### Issue 4: Counter Race Condition Risk

**Location**: `tasks.py` line 132-137

```python
current_count = conversation.get("followup_count_24h", 0)
api_client.update_conversation(
    conversation_id,
    followup_count_24h=current_count + 1
)
```

**Problem**: Read-modify-write without atomic operation. If two workers process the same conversation simultaneously, counts could be wrong.

**Impact**: Could lead to incorrect followup counts (rare but possible)

**Recommendation**: Use atomic increment on the database side, e.g., `followup_count_24h = followup_count_24h + 1`

---

### Issue 5: No Maximum Followup Limit After 6H

**Location**: `internals.py` followup buckets

**Problem**: After 6-hour followup (stage FOLLOWUP_6H), there's no transition to `GHOSTED` or `LOST`. The conversation stays active indefinitely.

**Impact**: No closure, stale conversations

**Recommendation**: Add scheduled transition to `GHOSTED` after 24-48 hours of no reply

---

### Issue 6: Hardcoded Timing Values

**Location**: `internals.py` lines 528-532

```python
buckets = [
    (10, 20, ConversationStage.FOLLOWUP_10M, 0),
    (180, 200, ConversationStage.FOLLOWUP_3H, 1),
    (360, 400, ConversationStage.FOLLOWUP_6H, 2),
]
```

**Problem**: Timings are hardcoded. If the `Followup` model was used, these would be configurable per-organization.

**Impact**: No flexibility for different follow-up strategies

**Recommendation**: Read timings from `Followup` model or add to Organization settings

---

## Summary Table

| Issue | Severity | Effort | Recommended Action |
|-------|----------|--------|-------------------|
| 1. Unused Followup model | Medium | Low | Remove or implement |
| 2. Unused scheduled_followup_at | Low | Low | Remove column |
| 3. Plain FOLLOWUP stage orphaned | Low | Low | Remove or map |
| 4. Counter race condition | Medium | Medium | Atomic DB increment |
| 5. No GHOSTED transition | High | Medium | Add 24h → GHOSTED |
| 6. Hardcoded timings | Medium | High | Make configurable |
