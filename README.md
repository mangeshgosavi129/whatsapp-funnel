# WhatsApp Funnel AI: Router-Agent Architecture

## 1. Project Overview
This project is an **AI-Driven Sales Agent** designed for WhatsApp. It uses a **Router-Agent Architecture** to separate high-level decision-making (The Brain) from response generation (The Mouth).

### Core Philosophy
- **Intentionality**: The AI never "just talks". It analyzes, decides, and then acts.
- **Micro-State Management**: Every conversation is tracked via explicit stages (`GREETING`, `QUALIFICATION`, `PRICING`, etc.).
- **Context Isolation**: Prompt logic is split to prevent "Context Pollution" (e.g., preventing the bot from trying to "close a deal" when it should be "greeting").
- **Self-Healing**: Automated background workers handle follow-ups and nudges if users (or the bot) go silent.

---

## 2. Architecture & Components

The system is composed of 4 main pillars:

### A. The Server (`/server`)
- **Framework**: FastAPI (Python).
- **Role**: The "Source of Truth". Handles DB connections, API endpoints, Websockets, and Authentication.
- **Database**: PostgreSQL (Stores Leads, Conversations, Messages, Configs).
- **WebSockets**: Real-time updates for the frontend (Lead replies, Status changes).

### B. The Worker (`/whatsapp_worker`)
- **Technique**: Celery + Redis (Async Processing).
- **Role**: Stateless processor for high-volume WhatsApp messages.
- **Flow**:
  1.  Receives Webhook from Meta.
  2.  Fetches Context (History, State) from Server API.
  3.  Runs the **HTL Pipeline**.
  4.  Sends Response via WhatsApp API.
  5.  Persists state back to Server.

### C. The Brain (`/llm`)
- **Role**: The Application Logic / Intelligence Layer.
- **Key Modules**:
  - `pipeline.py`: Orchestrator (Classify -> Generate -> Summarize).
  - `steps/classify.py`: **The Brain**. Decides Stage & Action.
  - `steps/generate.py`: **The Mouth**. Writes the actual text.
  - `prompts.py`: Transition Rules (Logic).
  - `prompts_registry.py`: Behavioral Personas (Tone/Style).

### D. The Frontend (`/frontend`)
- **Framework**: Next.js + React.
- **Role**: Dashboard for humans to monitor, intervene, and configure the bot.

---

## 3. The HTL Pipeline (Human Thinking Layer)

The "Human Thinking Layer" is the core AI logic. It mimics a human salesperson's thought process.

### Logical Data Flow (Example)

**Scenario**: User asks specifically about price during the qualification phase.

#### Step 0: Input Context
- **User Message**: "That sounds good, but how much does it cost?"
- **Current State**: `stage=QUALIFICATION`, `sentiment=neutral`.
- **History**: Bot asked "What volume do you need?" -> User answered "100 units".

#### Step 1: CLASSIFY (The Brain)
*Analysis & Decision Phase*
- **Input**:
    - `CLASSIFY_BASE_INSTRUCTIONS` (World-Class Strategist Persona).
    - `CLASSIFY_STAGE_INSTRUCTIONS[QUALIFICATION]` (Transition Rules).
    - **Rule Check**: "TRANSITION OUT OF qualification → pricing: User asks about cost/price".
- **LLM Output (JSON)**:
  ```json
  {
    "thought_process": "User is asking for price. Qualification is sufficient for a range quote.",
    "intent_level": "high",
    "user_sentiment": "curious",
    "new_stage": "PRICING",
    "action": "send_now"
  }
  ```

#### Step 2: GENERATE (The Mouth)
*Execution Phase*
- **Input**:
    - **New Stage**: `PRICING` (This loads the specific `PRICING` behavioral prompt from `prompts_registry.py`).
    - **Directive**: `GOAL: Communicate value. DO: Provide range/estimate.`
    - **Brain's Thought**: "User is asking for price..."
    - **Business Config**: "Pricing starts at $500/mo".
- **LLM Output (JSON)**:
  ```json
  {
    "message_text": "For 100 units, our pricing starts at approx $500/mo. Does that fit your budget?",
    "message_language": "en"
  }
  ```

#### Step 3: ACTION & SUMMARY
- **Action**: Message sent to WhatsApp immediately (Low latency).
- **State Update**: DB updated to `stage=PRICING`.
- **Background Summary**: "User asked price for 100 units. Bot quoted $500 start range." added to rolling summary.

---

## 4. Key Directories & Files

### `/llm` ( The Intelligence Core )
| File | Purpose |
|------|---------|
| `pipeline.py` | Main entry point (`run_pipeline`). Chains the steps. |
| `prompts.py` | **LOGIC PROMPTS**. Contains the "Transition Rules" (Step 1). Defines *When* to move stages. |
| `prompts_registry.py` | **BEHAVIOR PROMPTS**. Contains the "Personas" (Step 2). Defines *How* to speak at each stage. |
| `steps/classify.py` | Python implementation of the Brain step. |
| `steps/generate.py` | Python implementation of the Mouth step. |

### `/server` ( The Backend )
| File | Purpose |
|------|---------|
| `main.py` | FastAPI app entry point. |
| `routes/internals.py` | **Internal API**. Used by the Worker to fetch/write DB data securely without direct DB access. |
| `enums.py` | Shared definitions for `ConversationStage`, `IntentLevel`, etc. Critical for resolving LLM outputs. |

### `/whatsapp_worker` ( The Hands )
| File | Purpose |
|------|---------|
| `main.py` | Webhook receiver. Triggers pipeline. |
| `processors/context.py` | Builds the `PipelineInput` object from API data. |
| `processors/actions.py` | Handles side effects (DB updates, WebSocket events) *after* the pipeline runs. |

---

## 5. Development Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL
- Redis (for Celery)
- Ngrok (for local webhook testing)

### Installation
1.  **Python Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    Create `.env` based on `.env.example`.
    - `OPENAI_API_KEY`: Required for LLM.
    - `DATABASE_URL`: Postgres connection string.
    - `INTERNAL_API_SECRET`: Shared secret between Server and Worker.

3.  **Run Services**:
    
    **Terminal 1 (Server)**:
    ```bash
    uvicorn server.main:app --reload
    ```
    
    **Terminal 2 (Worker)**:
    ```bash
    celery -A whatsapp_worker.celery_app worker --loglevel=info -P solo
    ```
    *(Note: `-P solo` is for Windows compatibility)*

    **Terminal 3 (Frontend)**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

---

## 6. Important Context for AI Agents
If you are an AI assisting with this project, pay attention to:

1.  **Prompt Separation**:
    - **Never** put behavioral instructions (Tone, Style) in `prompts.py`. Put them in `prompts_registry.py`.
    - **Never** put logic rules (IF/THEN transitions) in `prompts_registry.py`. Put them in `prompts.py`.

2.  **Enum Synchronization**:
    - If you change a Stage in `server/enums.py`, you **must** update:
        - `CLASSIFY_STAGE_INSTRUCTIONS` in `llm/prompts.py`.
        - `STAGE_INSTRUCTIONS` in `llm/prompts_registry.py`.

3.  **Internal API Pattern**:
    - The Worker does not touch the DB. It calls `server/routes/internals.py`. If you need new data in the worker, add an Internal API route.
