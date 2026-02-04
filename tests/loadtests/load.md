# Load Test Analysis - WhatsApp Bot System

> **Test Date:** 2026-02-04  
> **Server:** 13.203.213.109 (4 Gunicorn workers)  
> **Database:** PostgreSQL (RDS)

---

## Test Results Summary

| Test | Duration | Total Requests | Error Rate | p95 Latency | Peak RPS |
|------|----------|---------------|------------|-------------|----------|
| **Baseline** | 10 min | 658 | **0.00%** ✓ | 20.61ms | 1 |
| **Burst** | 3 min | 16,194 | **0.88%** ✓ | 380.92ms | **92.76** |
| **Stress** | 9 min | 27,771 | **2.15%** ✓ | 53.89ms | 51.38 |

---

## System Capacity Estimates

### Raw Throughput

| Metric | Value |
|--------|-------|
| **Sustainable RPS** | ~50 requests/sec |
| **Peak RPS** (short bursts) | ~90 requests/sec |
| **Breaking Point** | ~100 concurrent connections (timeouts start) |

### Daily Message Capacity

Assuming 16-hour active window (8 AM - 12 AM):

| Scenario | Messages/Hour | Messages/Day |
|----------|---------------|--------------|
| **Conservative (30 RPS)** | 108,000 | **1.7M** |
| **Optimal (50 RPS)** | 180,000 | **2.9M** |
| **Peak (90 RPS)** | 324,000 | **5.2M** |

---

## Business Capacity Projections

### Key Assumptions

| Parameter | Value | Notes |
|-----------|-------|-------|
| Messages per lead per day | 15 | Includes both incoming + bot responses |
| API calls per message | 2-3 | Store message + update conversation |
| Peak hour multiplier | 3x | Traffic 3x average during peak hours |
| Active conversation ratio | 30% | 30% of leads are active daily |

### Client Capacity Estimates

Using **conservative 30 RPS** (accounting for peak hours and safety margin):

| Metric | Calculation | Capacity |
|--------|-------------|----------|
| **Daily API budget** | 30 × 3600 × 16 | 1,728,000 calls |
| **Messages/day** | 1.7M ÷ 2.5 API calls | **~700K messages** |
| **Active leads/day** | 700K ÷ 15 msgs | **~46,000 leads** |
| **Total leads** (30% active) | 46K ÷ 0.3 | **~150,000 leads** |

### Multi-Client Breakdown

| Scenario | Clients | Leads/Client | Active Leads/Day | Messages/Day |
|----------|---------|--------------|------------------|--------------|
| **Small Scale** | 10 | 5,000 | 1,500 | 22,500 |
| **Medium Scale** | 50 | 3,000 | 900 | 45,000 |
| **Current Max** | 100 | 1,500 | 450 | 45,000 |
| **System Limit** | 150 | 1,000 | 300 | 45,000 |

> **Sweet Spot:** 50-100 clients with ~3,000 total leads each

---

## Bottlenecks Identified

### 1. Database Connection Pool
- Under stress (100 VUs), some requests time out
- Likely hitting PostgreSQL connection limits

### 2. Single-Server Architecture
- 4 Gunicorn workers on single EC2 instance
- No horizontal scaling capability currently

### 3. Request Timeouts at Peak
- Max latency: 10s (timeout threshold)
- Occurs when VUs exceed 80-100

---

## Recommendations for Scaling

| Priority | Action | Expected Improvement |
|----------|--------|---------------------|
| **P0** | Increase DB connection pool | +20% throughput |
| **P1** | Add PostgreSQL read replicas | +50% read capacity |
| **P1** | Horizontal scaling (2 servers) | 2x throughput |
| **P2** | Add Redis caching for hot paths | +30% response time |
| **P2** | CDN for static assets | Reduce server load |

---

## Current System Rating

| Workload | Status | Notes |
|----------|--------|-------|
| **MVP / Pilot** (5-10 clients) | ✅ Excellent | No changes needed |
| **Early Stage** (50 clients) | ✅ Good | Monitor peak hours |
| **Growth** (100+ clients) | ⚠️ Marginal | Consider scaling |
| **Scale** (200+ clients) | ❌ At Risk | Requires infrastructure upgrade |

---

## Quick Reference

```
Current System Can Handle:
├── ~50 concurrent API requests/sec sustained
├── ~90 concurrent API requests/sec (short bursts)
├── ~700,000 messages/day
├── ~46,000 active conversations/day
└── ~150,000 total leads in database

Recommended Client Limits:
├── Pilot: 10 clients × 5,000 leads each
├── Standard: 50 clients × 3,000 leads each
└── Maximum: 100 clients × 1,500 leads each
```
