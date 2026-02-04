# Database Schema Design Flaws - Investigation

> **Status**: Investigation Only - No DB Changes Yet
> **Date**: 2025-02-05
> **Priority**: Medium-High

---

## 🔴 Critical: Duplicated State Fields

### Issue 1: `stage` / `intent_level` / `user_sentiment` Duplication

**Location**: 
- `Conversation` model (lines 76-79): `stage`, `intent_level`, `user_sentiment`
- `Lead` model (lines 196-198): `conversation_stage`, `intent_level`, `user_sentiment`

**Problem**:
- Same data stored in two places
- Synced manually via `actions.py` (lines 92-97) - can fail silently
- Frontend inconsistency: inbox uses `conv.stage`, leads page used `lead.conversation_stage`
- Manual edits in one place don't update the other

**Root Cause**: Unclear ownership of sales state - is it per-conversation or per-lead?

**Recommendation**:
```
Option A: Remove Lead.{conversation_stage, intent_level, user_sentiment}
          - Source of truth: Conversation model
          - Lead is just contact info, Conversation tracks sales state
          - Pro: Single source of truth
          - Con: Need to join conversations to get lead's current stage

Option B: If Lead needs these (e.g., multiple conversations per lead):
          - Make it computed/view from latest conversation
          - Or use DB triggers to auto-sync
```

---

## 🟡 Medium: Redundant Foreign Keys

### Issue 2: `Message.lead_id` Redundancy

**Location**: `Message` model (line 111)

**Problem**:
- `Message` has both `conversation_id` and `lead_id`
- `lead_id` is derivable via `conversation.lead_id`
- Creates potential for inconsistency

**Recommendation**:
```
Remove Message.lead_id
Access via: message.conversation.lead_id
```

### Issue 3: `Message.organization_id` Redundancy

**Location**: `Message` model (line 109)

**Problem**:
- `organization_id` is derivable via `conversation.organization_id`

**Recommendation**:
```
Remove Message.organization_id
Access via: message.conversation.organization_id
```

---

## 🟡 Medium: Legacy Fields

### Issue 4: `Template.content` Legacy Field

**Location**: `Template` model (line 153)

**Problem**:
- Comment says "Legacy field, keeping for compatibility"
- Primary content is in `components` (JSON)
- Potential confusion about which to use

**Recommendation**:
```
Migration plan:
1. Ensure all code uses `components`
2. Migrate existing `content` to `components` format
3. Remove `content` column
```

---

## 🟡 Medium: Missing Relationships

### Issue 5: Organization Missing Template/CTA/Lead Relationships

**Location**: `Organization` model (lines 30-46)

**Problem**:
- Only has `users` and `conversations` relationships
- Missing: `templates`, `ctas`, `leads`, `whatsapp_integrations`
- Makes navigation harder

**Recommendation**:
```python
# Add to Organization model:
templates = relationship("Template", back_populates="organization")
ctas = relationship("CTA", back_populates="organization")
leads = relationship("Lead", back_populates="organization")
whatsapp_integrations = relationship("WhatsAppIntegration", ...)
```

### Issue 6: Template/CTA/Lead Missing Back-References

**Problem**: These models have `organization_id` FK but no relationship defined

---

## 🟡 Medium: Unused/Underutilized Models

### Issue 7: Followup Model Unused

**Location**: `Followup` model (lines 166-179)

**Problem**:
- Model exists with `template_id`, `delay_hours`, `sequence_order` fields
- NEVER queried anywhere in codebase
- Followup logic uses hardcoded buckets in `internals.py` instead
- Was intended for configurable template-based followups

**Recommendation**:
```
Either:
- Remove Followup model (dead code) - SIMPLEST
- Or implement template-based follow-ups using this model
```

### Issue 7b: `Conversation.scheduled_followup_at` Unused

**Location**: `Conversation` model (line 95)

**Problem**:
- Column `scheduled_followup_at` is defined but never written to or queried
- Due-followup logic uses `last_bot_message_at` + bucket time windows instead
- Redundant field

**Recommendation**:
```
Remove column - not needed with current bucket-based approach
```

### Issue 8: Analytics Model Limited

**Location**: `Analytics` model (lines 209-219)

**Problem**:
- Only stores `total_conversations`, `total_messages`
- Frontend analytics calculates from conversations/leads directly
- This table might not be populated

**Recommendation**:
```
Either:
- Expand with useful pre-aggregated metrics
- Or remove if analytics computed on-the-fly
```

---

## 🟢 Minor: Missing Indexes

### Issue 9: Missing Query Optimization Indexes

**Suggested Indexes**:
```python
# Lead
Index("ix_leads_org_phone", Lead.organization_id, Lead.phone)

# Conversation  
Index("ix_conv_org_lead", Conversation.organization_id, Conversation.lead_id)
Index("ix_conv_last_bot_msg", Conversation.last_bot_message_at)  # for followup queries

# Message
Index("ix_msg_conv_created", Message.conversation_id, Message.created_at)
```

---

## 🟢 Minor: Schema Hygiene

### Issue 10: Inconsistent Nullable Patterns

- Some `updated_at` have `onupdate=func.now()` but are nullable (null until first update)
- Some FKs are optional when they shouldn't be

### Issue 11: Missing Unique Constraints

```python
# Should add:
UniqueConstraint(Lead.organization_id, Lead.phone)  # One lead per phone per org
UniqueConstraint(WhatsAppIntegration.phone_number_id)  # One integration per phone
```

---

## Action Plan

1. **Phase 1 (Frontend Fix)** ✅ DONE
   - Modified `leads/page.tsx` to use `conv.stage` as source of truth

2. **Phase 2 (Backend Sync Improvement)**
   - Make lead sync transactional with conversation update
   - Add retry/rollback logic

3. **Phase 3 (Schema Cleanup)**
   - Create Alembic migration to remove duplicated Lead fields
   - Update all code to fetch from Conversation
   - Add suggested indexes

4. **Phase 4 (Dead Code Cleanup)**
   - Remove unused Followup/Analytics if confirmed unused
   - Remove Template.content legacy field

---

## Files to Modify (When Ready)

- `server/models.py` - Remove duplicated fields, add relationships
- `server/schemas.py` - Update schemas to match
- `server/routes/*.py` - Update endpoints
- `whatsapp_worker/processors/actions.py` - Remove lead sync code
- `frontend/**/page.tsx` - Already fetching from conversations
