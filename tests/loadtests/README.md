# k6 Load Testing for WhatsApp Bot

Load and stress testing framework using k6 to validate API throughput and database performance.

## Prerequisites

```bash
# Install k6
brew install k6
```

## Configuration

Set environment variables before running tests:

```bash
export INTERNAL_SECRET="your-internal-secret"
export AUTH_TOKEN="your-jwt-token"          # For external API tests
export TEST_ORG_ID="your-org-uuid"          # Existing org from database
export TEST_CONV_ID="your-conv-uuid"        # Existing conversation (optional)
export TEST_LEAD_ID="your-lead-uuid"        # Existing lead (optional)
```

## Test Scenarios

### 1. Baseline Test (~1 RPS, 10-15 min)
Validates system stability under normal load.

```bash
k6 run scenarios/baseline.js
```

### 2. Burst Test (30-50 RPS, 3 min)
Simulates realistic WhatsApp bursty traffic patterns.

```bash
k6 run scenarios/burst.js
```

### 3. Stress Test (100 VUs, 9 min)
Finds system breaking points under extreme load.

```bash
k6 run scenarios/stress.js
```

## Target Thresholds

| Test | p95 Latency | Error Rate |
|------|-------------|------------|
| Baseline | < 500ms | < 0.1% |
| Burst | < 800ms | < 1% |
| Stress | < 1500ms | < 5% |

## Results

Test results are saved to `loadtests/results/`:
- `baseline-summary.json`
- `burst-summary.json`
- `stress-summary.json`

## API Endpoints Tested

**Internal APIs** (`/internals/*`):
- `POST /messages/incoming` - Store incoming messages
- `POST /messages/outgoing` - Store outgoing messages
- `GET /conversations/{id}` - Fetch conversation
- `PATCH /conversations/{id}` - Update conversation
- `GET /conversations/{id}/messages` - Get message history

**External APIs**:
- `GET /conversations/` - List conversations
- `GET /dashboard/stats` - Dashboard statistics
