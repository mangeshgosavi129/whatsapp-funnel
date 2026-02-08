# Whatsapp-Funnel

## 📖 Project Overview
**Whatsapp-Funnel** is a robust, production-ready WhatsApp automation platform designed to handle complex conversational flows using a **4-Stage Human-in-the-Loop (HTL) LLM Pipeline**. 

Unlike simple chatbots, this system observes, reasons, plans, and then acts. It features a scalable architecture with a **FastAPI** backend, **AWS SQS** for reliable message queuing, and a decoupled **Worker** for asynchronous processing.

### Key Features
- **4-Stage LLM Pipeline**: Eyes (Observe) → Brain (Decide) → Mouth (Respond) → Memory (Summarize).
- **Asynchronous Architecture**: Decouples webhook reception from processing using AWS SQS.
- **Human-in-the-Loop**: Seamlessly hands off conversations to humans when needed.
- **Scalable**: Built with FastAPI and designed for serverless (AWS Lambda) or containerized deployment.
- **Observability**: Structured logging and detailed pipeline tracing.

---

## 📂 Folder Structure

The project is organized into distinct services to maintain separation of concerns:

- **`server/`**: The core Backend API built with FastAPI. Handles database interactions, API routes, and business logic.
- **`llm/`**: Contains the intelligence of the system.
    - `steps/`: Individual steps of the pipeline (Eyes, Brain, Mouth, Memory).
    - `prompts.py`: Centralized prompt management.
    - `pipeline.py`: Orchestrator for the HTL flow.
- **`whatsapp_worker/`**: A standalone worker service that:
    - Long-polls AWS SQS for incoming messages.
    - Executes the `llm` pipeline.
    - Sends responses back via the WhatsApp API.
- **`whatsapp_receive/`**: A lightweight webhook receiver (likely deployed as a Lambda function) that validates incoming WhatsApp webhooks and pushes them to SQS.
- **`frontend/`**: The user interface for managing conversations, analytics, and settings.
- **`scripts/`**: Utility scripts for deployment, testing, or maintenance.

---

## 🔌 API Documentation

The backend API is structured around RESTful principles. The main `server` application invokes the following routers:

| Prefix | Tag | Description |
| :--- | :--- | :--- |
| `/auth` | Authentication | User login, registration, and token management. |
| `/dashboard` | Dashboard | Aggregated metrics for the main dashboard. |
| `/leads` | Leads | Management of leads (potential customers) captured via WhatsApp. |
| `/conversations` | Conversations | Retrieving and managing chat histories. |
| `/messages` | Messages | Sending manual messages or retrieving specific message details. |
| `/ctas` | CTAs | Call-to-Action management and tracking. |
| `/templates` | Templates | WhatsApp template message management. |
| `/analytics` | Analytics | Detailed performance metrics and reporting. |
| `/settings` | Settings | System and user configuration. |
| `/users` | Users | User management (admin tasks). |
| `/organisations` | Organisations | Multi-tenancy support for different business units. |
| `/internals` | Internals | Internal tools or system-level endpoints. |
| `/debug` | Debug | Endpoints for testing and debugging system internals. |

> **Note**: Interactive API documentation (Swagger UI) is available at `/docs` when running the server locally.

---

## 🧠 HTL Pipeline: The Core Intelligence

The system processes every message through a 4-step pipeline to ensure high-quality, safe, and context-aware responses.

### 1. Eyes (The Observer)
- **Role**: Analyzes the raw conversation.
- **Output**: Determines `Intent`, `Sentiment`, `Risk Flags`, and generates a `Situation Summary`.
- **Why**: Ensures the bot understands *before* it tries to solve.

### 2. Brain (The Strategist)
- **Role**: Decides *what* to do based on the Eyes' observation.
- **Output**: `Implementation Plan`, `Decision Action` (e.g., RESPOND, IGNORE, WAIT, HUMAN_HANDOFF).
- **Why**: Separates strategy from execution. Prevents hallucinations by planning first.

### 3. Mouth (The Speaker)
- **Role**: Generates the final response text *only if* the Brain decided to respond.
- **Output**: The actual text message sent to the user.
- **Why**: Ensures the tone, style, and content match the Brain's plan.

### 4. Memory (The Scribe)
- **Role**: Runs in the background *after* the response.
- **Action**: Updates the `Rolling Summary` of the conversation.
- **Why**: Keeps the context window small and efficient by summarizing past events.

---

## 📚 RAG Setup (Knowledge Base)

The system implements a **Retrieval-Augmented Generation (RAG)** pipeline to ground LLM responses in business-specific knowledge. It uses a **Hybrid Search** approach combining semantic vector search with keyword search.

### 1. Architecture

| Component | Technology | Configuration |
| :--- | :--- | :--- |
| **Embedding Model** | Google Gemini | `models/gemini-embedding-001` |
| **Dimensionality** | MRL (Matryoshka) | **768 dimensions** (Sliced from 3072d) |
| **Vector Store** | PostgreSQL | `pgvector` extension |
| **Search Strategy** | Hybrid (Vector + Keyword) | Cosine Similarity + `tsvectors` |

### 2. Data Flow

#### Ingestion (Frontend -> Backend -> DB)
1. **Upload**: User uploads a PDF/MD/TXT file via `Settings > Knowledge Base`.
2. **Processing** (`llm/knowledge.py`):
   - **Text Extraction**: Uses `pypdf` for PDFs.
   - **Chunking**: Splits text into 1000-character chunks with 200-character overlap using `RecursiveCharacterTextSplitter`.
   - **Embedding**: Generates embeddings using `models/gemini-embedding-001` with `task_type="retrieval_document"`.
   - **Optimization**: Slices the 3072d output to **768d** and applies **L2 Normalization**.
3. **Storage**: Saves the chunk text, 768d vector, and metadata to the `knowledge_items` table in Postgres.

#### Retrieval (Brain -> DB -> Context)
1. **Query**: The `Brain` step (`llm/steps/brain.py`) extracts a search query from the conversation.
2. **Embedding**: Embeds the query using `models/gemini-embedding-001` with `task_type="retrieval_query"`.
3. **Search**:
   - **Vector Search**: Finds top-k chunks by Cosine Similarity (using `<=>` operator in pgvector).
   - **Keyword Search**: Uses Postgres `ts_rank` for keyword matching (Planned/Optional).
4. **Context Injection**: The most relevant chunks are injected into the LLM's system prompt under a `## Relevant Business Knowledge` section.

### 3. Database Schema

The `knowledge_items` table is optimized for vector search:

```sql
CREATE TABLE knowledge_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    title VARCHAR NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768), -- Gemini MRL 768d
    search_vector TSVECTOR, -- For hybrid keyword search
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4. Setup & Configuration

**Prerequisites:**
- **PostgreSQL**: Must have `pgvector` extension installed (`CREATE EXTENSION vector;`).
- **Google API Key**: Must be set in `.env` as `GOOGLE_API_KEY`.

**Environment Variables:**
```bash
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/whatsapp_funnel
```

### 5. API Endpoints

- **GET /knowledge/**: List all uploaded documents for the organization.
- **POST /knowledge/ingest**: Upload a file (PDF/MD/TXT) for ingestion.
- **DELETE /knowledge/{id}**: Delete a specific document and its chunks.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Docker (optional)
- AWS Credentials (for SQS/S3/Bedrock if used)

### Running Locally
1. **Start the Server**:
   ```bash
   uvicorn server.main:app --reload
   ```
2. **Start the Worker**:
   ```bash
   python -m whatsapp_worker.main
   ```
3. **Start Frontend** (if applicable):
   ```bash
   cd frontend && npm run dev
   ```

---
*Built with ❤️ by the Whatsapp-Funnel Team*
