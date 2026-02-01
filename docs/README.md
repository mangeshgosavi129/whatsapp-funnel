# WhatsApp Sales Funnel - AI Chatbot Platform

> **A production-grade WhatsApp AI sales agent powered by the Human Thinking Layer (HTL) - an intelligent 4-step LLM pipeline that thinks, adapts, and sells like your best human sales rep.**

![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![LLM](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-green)
![Database](https://img.shields.io/badge/Database-PostgreSQL-blue)
![Queue](https://img.shields.io/badge/Queue-AWS%20SQS-orange)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [HTL Pipeline Deep Dive](#htl-pipeline-deep-dive)
- [Data Flow Example](#data-flow-example)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Changelog](#changelog)

---

## Overview

This platform enables businesses to deploy AI-powered sales agents on WhatsApp. Each client organization gets their own WhatsApp number with an intelligent chatbot that:

- **Engages prospects** like a human sales representative
- **Detects buying signals** and objections (even indirect ones)
- **Makes strategic decisions** about when to respond, wait, or escalate
- **Adapts its approach** based on sentiment and intent
- **Schedules intelligent follow-ups** without being spammy
- **Hands off to humans** when necessary

### The Vision: Human Thinking Layer (HTL)

HTL is not a simple chatbot. It's a **digital sales mind** that processes each conversation through 4 intelligent steps:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   ANALYZE   │───▶│   DECIDE    │───▶│  GENERATE   │───▶│  SUMMARIZE  │
│             │    │             │    │             │    │             │
│ Understand  │    │ Choose      │    │ Write       │    │ Update      │
│ situation   │    │ action      │    │ message     │    │ context     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Features

### 🤖 AI Sales Agent
- Natural, human-like conversations
- Multi-language support
- Context-aware responses (remembers conversation history)
- ROI and value proposition communication

### 🧠 Intelligent Decision Making
- **SEND_NOW**: Respond immediately to high-intent questions
- **WAIT_SCHEDULE**: Schedule strategic follow-ups
- **HANDOFF_HUMAN**: Escalate complex/sensitive situations

### 📊 Conversation State Tracking
- Conversation stages: `greeting` → `qualification` → `pricing` → `cta` → `closed`
- Intent levels: `unknown` → `low` → `medium` → `high` → `very_high`
- Sentiment detection: `positive`, `neutral`, `hesitant`, `negative`, `confused`

### 🛡️ Guardrails & Compliance
- Anti-spam protection (limits follow-ups per 24h)
- WhatsApp 24-hour window detection
- Template requirement flagging
- Self-check for policy violations

### 📱 Multi-Tenant Architecture
- Multiple organizations on single platform
- Each org has their own WhatsApp number
- Isolated conversations and data

### ⏰ Scheduled Follow-ups
- Celery beat for reliable scheduling
- Intelligent timing based on intent and sentiment
- Automatic cancellation when user responds

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 EXTERNAL                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐           │
│    │   WhatsApp   │         │   WhatsApp   │         │   WhatsApp   │           │
│    │   Number A   │         │   Number B   │         │   Number C   │           │
│    │  (Client 1)  │         │  (Client 2)  │         │  (Client 3)  │           │
│    └──────┬───────┘         └──────┬───────┘         └──────┬───────┘           │
│           │                        │                        │                    │
│           └────────────────────────┼────────────────────────┘                    │
│                                    │                                             │
│                                    ▼                                             │
│                          ┌─────────────────┐                                     │
│                          │  Meta Webhook   │                                     │
│                          └────────┬────────┘                                     │
│                                   │                                              │
└───────────────────────────────────┼──────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼──────────────────────────────────────────────┐
│                               INGRESS                                            │
├───────────────────────────────────┼──────────────────────────────────────────────┤
│                                   ▼                                              │
│                    ┌───────────────────────────┐                                 │
│                    │    WhatsApp Receiver      │                                 │
│                    │    (FastAPI Endpoint)     │                                 │
│                    │    - Validates webhook    │                                 │
│                    │    - Pushes to SQS        │                                 │
│                    └─────────────┬─────────────┘                                 │
│                                  │                                               │
│                                  ▼                                               │
│                    ┌───────────────────────────┐                                 │
│                    │       AWS SQS Queue       │                                 │
│                    │    (Message Buffer)       │                                 │
│                    └─────────────┬─────────────┘                                 │
│                                  │                                               │
└──────────────────────────────────┼───────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────────┐
│                              PROCESSING                                          │
├──────────────────────────────────┼───────────────────────────────────────────────┤
│                                  ▼                                               │
│                    ┌───────────────────────────┐                                 │
│                    │    WhatsApp Worker        │                                 │
│                    │    (Long-polling SQS)     │                                 │
│                    └─────────────┬─────────────┘                                 │
│                                  │                                               │
│            ┌─────────────────────┼─────────────────────┐                         │
│            │                     │                     │                         │
│            ▼                     ▼                     ▼                         │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│   │ Context Builder │  │  HTL Pipeline   │  │ Action Handler  │                  │
│   │ - Get org/lead  │  │  - 4-step LLM   │  │ - Send message  │                  │
│   │ - Get messages  │  │  - See below    │  │ - Schedule      │                  │
│   │ - Build context │  │                 │  │ - Escalate      │                  │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────────┐
│                              PERSISTENCE                                         │
├──────────────────────────────────┼───────────────────────────────────────────────┤
│                                  ▼                                               │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│   │ PostgreSQL  │  │    Redis    │  │   Celery    │  │   Groq      │             │
│   │ - Orgs      │  │ - Celery    │  │ - Beat      │  │ - LLM API   │             │
│   │ - Leads     │  │   broker    │  │ - Worker    │  │ - gpt-oss-20b             │
│   │ - Messages  │  │             │  │             │  │             │             │
│   │ - Events    │  │             │  │             │  │             │             │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Technical Implementation Details

### 1. The Distributed Worker Pattern
The system uses a strict **separation of concerns** between the `server` (state management) and `whatsapp_worker` (business logic).

- **Worker Isolation**: The worker (`whatsapp_worker/`) acts as a "brain" that runs independently. It has **no direct database access**.
- **Internal API**: The worker interacts with the database exclusively through the `InternalsAPIClient` (`whatsapp_worker/processors/api_client.py`), which calls secured endpoints on the server (`server/routes/internals.py`). This ensures all DB logic remains in the monolithic server while allowing the worker to scale horizontally.
- **Security**: Internal communications are secured via an `X-Internal-Secret` header.

### 2. The HTL Pipeline (Logic Core)
The Human Thinking Layer is implemented as a pure-logic library in `llm/`. It is stateless and decoupled from the transport layer (WhatsApp).

- **Context Retrieval**: When a message arrives, the worker constructs a `PipelineInput` object containing the `rolling_summary`, `last_3_messages`, and current `intent_level`.
- **Latency Optimization**: The `analyze` and `decide` steps are optimized for speed (~200ms) to ensure the `decide` step can determine if an immediate response is even necessary.
- **Token Efficiency**: The `summarize` step continually compresses the conversation history into a `rolling_summary`. This means the context window for the LLM never grows linearly with conversation length, keeping costs flat and low.

### 3. Asynchronous Data Flow
1.  **Ingestion**: `whatsapp_receive` is a lightweight buffer. It performs no logic other than signature verification and SQS pushing.
2.  **Debouncing**: The worker implements a logical debounce (`_message_buffer` in `main.py`) to handle users sending multiple short messages (e.g., "Hi", "Are you available?", "I need help") as a single context block.
3.  **Reliability**: Failed processing in the worker does not delete the SQS message, allowing for automatic retries via visibility timeouts.


---

## HTL Pipeline Deep Dive

The Human Thinking Layer processes each message through 4 specialized LLM calls:

### Step 1: ANALYZE 🔍

**Purpose:** Understand the conversation context

**Input:**
- Rolling summary (80-200 words)
- Last 3 messages
- Current stage, intent, sentiment
- Timing information

**Output:**
```json
{
  "situation_summary": "Lead asked about pricing for premium plan",
  "lead_goal_guess": "Evaluate if pricing fits budget",
  "missing_info": ["budget", "timeline"],
  "detected_objections": ["price_concern"],
  "stage_recommendation": "pricing",
  "risk_flags": {
    "spam_risk": "low",
    "policy_risk": "low",
    "hallucination_risk": "low"
  },
  "need_kb": {
    "required": true,
    "query": "premium plan pricing"
  },
  "confidence": 0.85
}
```

### Step 2: DECIDE 🧠

**Purpose:** Choose what action to take

**Decision Matrix:**

| Scenario | Action | Timing |
|----------|--------|--------|
| High intent + direct question | SEND_NOW | Immediate |
| WhatsApp window closed | WAIT_SCHEDULE | Use template |
| High spam risk | WAIT_SCHEDULE | 6-24 hours |
| User annoyed/frustrated | WAIT_SCHEDULE | 24+ hours |
| Complex query/negotiation | HANDOFF_HUMAN | Immediate |
| Low confidence analysis | HANDOFF_HUMAN | Immediate |

**Output:**
```json
{
  "action": "SEND_NOW",
  "why": "Direct pricing question with high intent",
  "next_stage": "pricing",
  "recommended_cta": null,
  "followup_in_minutes": 0,
  "template_required": false
}
```

### Step 3: GENERATE ✍️

**Purpose:** Write the actual message (only runs if action = SEND_NOW)

**Constraints:**
- Max 80 words
- Max 1 question per message
- Match language preference
- Never claim to be human
- Never guarantee outcomes

**Output:**
```json
{
  "message_text": "Great question! Our premium plan is ₹4,999/month and includes unlimited users. What's your current team size?",
  "message_language": "en",
  "cta_type": null,
  "next_stage": "pricing",
  "state_patch": {
    "intent_level": "high",
    "user_sentiment": "curious"
  },
  "self_check": {
    "guardrails_pass": true,
    "violations": []
  }
}
```

### Step 4: SUMMARIZE 📝

**Purpose:** Update rolling summary for future context (always runs)

**Output:**
```json
{
  "updated_rolling_summary": "Lead (unknown name) inquired about pricing. Bot shared premium plan price (₹4,999/month) and asked about team size. Lead seems interested. Stage: pricing. Intent: high. No objections yet."
}
```

---

## Data Flow Example

Let's trace a complete message through the system:

### Scenario: New lead asks "What's your pricing?"

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. USER SENDS MESSAGE                                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   WhatsApp User ──────▶ Meta Cloud API ──────▶ Webhook Endpoint     │
│                                                                      │
│   Payload:                                                           │
│   {                                                                  │
│     "from": "919876543210",                                          │
│     "text": { "body": "What's your pricing?" },                      │
│     "metadata": { "phone_number_id": "123456789" }                   │
│   }                                                                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. WHATSAPP RECEIVER                                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   - Validates signature                                              │
│   - Pushes to SQS queue                                              │
│                                                                      │
│   SQS Message:                                                       │
│   {                                                                  │
│     "entry": [{"changes": [{"value": {...}}]}]                       │
│   }                                                                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. WHATSAPP WORKER (handle_webhook)                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   a) Parse message                                                   │
│      sender_phone = "919876543210"                                   │
│      phone_number_id = "123456789"                                   │
│      text = "What's your pricing?"                                   │
│                                                                      │
│   b) Get organization by phone_number_id                             │
│      → Organization: "Acme Corp"                                     │
│                                                                      │
│   c) Get or create lead                                              │
│      → Lead: { id: "abc123", phone: "919876543210" }                 │
│                                                                      │
│   d) Get or create conversation                                      │
│      → Conversation: {                                               │
│          id: "conv456",                                              │
│          stage: "greeting",                                          │
│          mode: "bot",                                                │
│          rolling_summary: ""                                         │
│        }                                                             │
│                                                                      │
│   e) Store incoming message                                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 4. CHECK MODE                                                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   if mode == "human":                                                │
│       → Store message, send WebSocket notification, return           │
│                                                                      │
│   if mode == "bot":                                                  │
│       → Continue to HTL Pipeline                                     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 5. BUILD PIPELINE CONTEXT                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   PipelineInput:                                                     │
│   {                                                                  │
│     "business_name": "Acme Corp",                                    │
│     "rolling_summary": "",                                           │
│     "last_3_messages": [                                             │
│       {"sender": "lead", "text": "What's your pricing?", ...}        │
│     ],                                                               │
│     "conversation_stage": "greeting",                                │
│     "intent_level": "unknown",                                       │
│     "user_sentiment": "neutral",                                     │
│     "timing": {                                                      │
│       "now_local": "2026-01-22T19:00:00+05:30",                      │
│       "whatsapp_window_open": true                                   │
│     },                                                               │
│     "nudges": { "followup_count_24h": 0, "total_nudges": 0 }         │
│   }                                                                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 6. HTL PIPELINE EXECUTION                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   STEP 1: ANALYZE (Groq API call ~200ms)                             │
│   ─────────────────────────────────                                  │
│   Output: {                                                          │
│     situation_summary: "New lead asking about pricing",              │
│     stage_recommendation: "pricing",                                 │
│     confidence: 0.9                                                  │
│   }                                                                  │
│                                                                      │
│   STEP 2: DECIDE (Groq API call ~150ms)                              │
│   ─────────────────────────────────                                  │
│   Output: {                                                          │
│     action: "SEND_NOW",                                              │
│     next_stage: "pricing"                                            │
│   }                                                                  │
│                                                                      │
│   STEP 3: GENERATE (Groq API call ~200ms)                            │
│   ─────────────────────────────────                                  │
│   Output: {                                                          │
│     message_text: "Hi! Our plans start at ₹999/month...",            │
│     state_patch: { intent_level: "medium" }                          │
│   }                                                                  │
│                                                                      │
│   STEP 4: SUMMARIZE (Groq API call ~150ms)                           │
│   ─────────────────────────────────                                  │
│   Output: {                                                          │
│     updated_rolling_summary: "New lead asked about pricing..."       │
│   }                                                                  │
│                                                                      │
│   Total: ~700ms, ~1500 tokens                                        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 7. HANDLE PIPELINE RESULT                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   - Update conversation stage: greeting → pricing                    │
│   - Update intent_level: unknown → medium                            │
│   - Update rolling_summary                                           │
│   - Store outgoing message in database                               │
│   - Log pipeline event                                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 8. SEND WHATSAPP RESPONSE                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   POST https://graph.facebook.com/v18.0/123456789/messages           │
│   {                                                                  │
│     "messaging_product": "whatsapp",                                 │
│     "to": "919876543210",                                            │
│     "type": "text",                                                  │
│     "text": { "body": "Hi! Our plans start at ₹999/month..." }       │
│   }                                                                  │
│                                                                      │
│   ✅ Message delivered to user                                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Core Tables

```
┌─────────────────────┐       ┌─────────────────────┐
│    organizations    │       │        users        │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │───┐   │ id (PK)             │
│ name                │   │   │ organization_id (FK)│───┐
│ is_active           │   │   │ name                │   │
│ created_at          │   │   │ email               │   │
└─────────────────────┘   │   │ hashed_password     │   │
                          │   └─────────────────────┘   │
                          │                             │
                          ▼                             │
┌─────────────────────────────────────────────────────────────────────┐
│                          leads                                       │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ organization_id (FK) ──────────────────────────────────────────────┘ │
│ name, phone, email, company                                          │
│ conversation_stage, intent_level, user_sentiment                     │
│ created_at, updated_at                                               │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       conversations                                  │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ organization_id (FK), lead_id (FK), cta_id (FK)                      │
│ stage, intent_level, mode, user_sentiment                            │
│ rolling_summary, last_message                                        │
│ last_message_at, last_user_message_at, last_bot_message_at           │
│ followup_count_24h, total_nudges, scheduled_followup_at              │
│ created_at, updated_at                                               │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         messages                                     │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ organization_id (FK), conversation_id (FK), lead_id (FK)             │
│ message_from (LEAD/BOT/HUMAN)                                        │
│ content, status                                                      │
│ created_at                                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### HTL Pipeline Tables

```
┌─────────────────────────────────────────────────────────────────────┐
│                      scheduled_actions                               │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ conversation_id (FK), organization_id (FK)                           │
│ scheduled_at (DateTime)                                              │
│ status (PENDING/EXECUTED/CANCELLED)                                  │
│ action_type, action_context                                          │
│ executed_at, created_at                                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     conversation_events                              │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ conversation_id (FK)                                                 │
│ event_type, pipeline_step                                            │
│ input_summary, output_summary                                        │
│ latency_ms, tokens_used                                              │
│ created_at                                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
whatsapp-funnel/
│
├── server/                      # FastAPI backend
│   ├── main.py                  # App entry point
│   ├── config.py                # Environment configuration
│   ├── database.py              # SQLAlchemy setup
│   ├── models.py                # Database models
│   ├── schemas.py               # Pydantic schemas
│   ├── enums.py                 # Enum definitions
│   ├── dependencies.py          # FastAPI dependencies
│   ├── security.py              # JWT authentication
│   ├── routes/                  # API endpoints
│   │   ├── auth.py
│   │   ├── conversations.py
│   │   ├── messages.py
│   │   ├── leads.py
│   │   ├── analytics.py
│   │   └── ...
│   └── services/                # Business logic
│       ├── websocket_manager.py
│       └── websocket_events.py
│
├── llm/                         # HTL Pipeline
│   ├── __init__.py
│   ├── main.py                  # Module exports
│   ├── config.py                # LLM configuration
│   ├── schemas.py               # Pipeline I/O schemas
│   ├── prompts.py               # LLM prompts
│   ├── pipeline.py              # Pipeline orchestrator
│   └── steps/                   # Individual steps
│       ├── __init__.py
│       ├── analyze.py           # Step 1
│       ├── decide.py            # Step 2
│       ├── generate.py          # Step 3
│       └── summarize.py         # Step 4
│
├── whatsapp_worker/             # Message processor
│   ├── __init__.py
│   ├── main.py                  # SQS polling loop
│   ├── config.py                # Worker configuration
│   ├── context.py               # Context builder
│   ├── actions.py               # Result handler
│   ├── send.py                  # WhatsApp API client
│   ├── tasks.py                 # Celery tasks
│   └── processors/
│       └── llm.py
│
├── whatsapp_receive/            # Webhook receiver
│   ├── main.py
│   ├── queue.py                 # SQS publisher
│   └── security.py              # Signature validation
│
├── tests/                       # Test suite
│
├── .env.example                 # Environment template
├── requirements.txt             # Python dependencies
├── README.md                    # This file
└── alembic/                     # Database migrations
```

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- AWS Account (for SQS)
- Groq API Key
- Meta WhatsApp Business API Access

### 1. Clone Repository

```bash
git clone https://github.com/your-org/whatsapp-funnel.git
cd whatsapp-funnel
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/whatsapp_funnel

# AWS SQS
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
SQS_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/123/queue-name

# LLM (Groq)
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
LLM_MODEL=llama-3.3-70b-versatile

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key
```

### 5. Initialize Database

```bash
# Create database
createdb whatsapp_funnel

# Run migrations
alembic upgrade head
```

### 6. Create Initial Migration (if needed)

```bash
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

---

## Running the Application

You need to run 4 services:

### Terminal 1: FastAPI Server

```bash
uvicorn server.main:app --reload --port 8000
```

### Terminal 2: WhatsApp Worker

```bash
python -m whatsapp_worker.main
```

### Terminal 3: Celery Worker

```bash
celery -A whatsapp_worker.tasks worker --loglevel=info
```

### Terminal 4: Celery Beat (Scheduler)

```bash
celery -A whatsapp_worker.tasks beat --loglevel=info
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## API Reference

### Authentication

```
POST /auth/login
POST /auth/signup/create-org
POST /auth/signup/join-org
```

### Conversations

```
GET  /conversations/
GET  /conversations/{id}/messages
POST /conversations/{id}/takeover
POST /conversations/{id}/release
```

### Messages

```
POST /messages/send
```

### Leads

```
GET    /leads/
POST   /leads/create
PUT    /leads/{id}
DELETE /leads/{id}
```

### Analytics

```
GET /analytics/
GET /dashboard/stats
```

Full API documentation available at: `http://localhost:8000/docs`

---

## Configuration

### LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Groq API key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model to use |
| `LLM_MAX_TOKENS` | `500` | Max response tokens |
| `LLM_TEMPERATURE` | `0.3` | Response randomness |
| `LLM_TIMEOUT` | `30` | API timeout (seconds) |

### Pipeline Tuning

| Setting | Location | Description |
|---------|----------|-------------|
| Max words per message | `PipelineInput.max_words` | Default: 80 |
| Questions per message | `PipelineInput.questions_per_message` | Default: 1 |
| Debounce window | `whatsapp_worker/main.py` | Default: 5 seconds |

### Anti-Spam

| Setting | Location | Description |
|---------|----------|-------------|
| Max follow-ups/24h | Conversation model | Tracked per conversation |
| WhatsApp window | `context.py` | 24 hours from last user message |

---

## Changelog

### v2.0.0 - HTL Pipeline (2026-01-22)

#### Added
- **HTL Pipeline** - 4-step LLM processing (Analyze → Decide → Generate → Summarize)
- **New LLM Module** (`llm/`)
  - `config.py` - Groq configuration
  - `schemas.py` - Pydantic I/O models
  - `prompts.py` - Token-optimized prompts
  - `pipeline.py` - Orchestrator
  - `steps/analyze.py` - Situation analysis
  - `steps/decide.py` - Action decision
  - `steps/generate.py` - Message generation
  - `steps/summarize.py` - Summary update
- **WhatsApp Worker Enhancements** (`whatsapp_worker/`)
  - `context.py` - Pipeline context builder
  - `actions.py` - Result handler
  - `tasks.py` - Celery tasks for scheduled follow-ups
- **New Enums**
  - `DecisionAction` - SEND_NOW, WAIT_SCHEDULE, HANDOFF_HUMAN
  - `RiskLevel` - LOW, MEDIUM, HIGH
  - `PipelineStep` - ANALYZE, DECIDE, GENERATE, SUMMARIZE
  - `ScheduledActionStatus` - PENDING, EXECUTED, CANCELLED
- **New Database Tables**
  - `scheduled_actions` - For Celery beat follow-ups
  - `conversation_events` - Pipeline audit log
- **New Conversation Fields**
  - `last_user_message_at` - For WhatsApp window calculation
  - `last_bot_message_at` - For timing decisions
  - `followup_count_24h` - Anti-spam tracking
  - `total_nudges` - Total follow-up count
  - `scheduled_followup_at` - Next scheduled follow-up

#### Changed
- `ConversationMode` - Reduced from 4 to 2 values (BOT, HUMAN)
- `whatsapp_worker/main.py` - Complete refactor with HTL integration
- `whatsapp_worker/send.py` - Updated function signature
- `.env.example` - Added LLM and Celery configuration
- `requirements.txt` - Added openai, celery, redis dependencies

#### Technical Details
- **Cost**: ~$0.00035 per message (~$3.50/day for 10,000 messages)
- **Latency**: ~700ms total pipeline execution
- **Tokens**: ~1,500 per full pipeline run

---

## License

Proprietary - All rights reserved.

---

## Support

For issues and feature requests, contact: [your-email@example.com]