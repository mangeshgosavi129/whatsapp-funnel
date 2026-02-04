/**
 * Burst Traffic Test
 * Purpose: Simulate realistic WhatsApp bursty traffic patterns
 * 
 * Duration: 2-5 minutes per burst
 * Rate: 30 requests/second during bursts
 * VUs: 30-50 concurrent
 * Pattern: 30s bursts with 10s pauses
 * 
 * NOTE: This test only hits database/API layer - NO WhatsApp messages are sent.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { config, getInternalHeaders } from '../config.js';
import {
    createIncomingMessagePayload,
    createOutgoingMessagePayload,
    createLeadPayload,
    createConversationPayload,
} from '../fixtures/test-data.js';

// Custom metrics
const errorRate = new Rate('errors');
const burstLatency = new Trend('burst_latency');
const messagesProcessed = new Counter('messages_processed');

// Test configuration
export const options = {
    scenarios: {
        burst_traffic: {
            executor: 'ramping-arrival-rate',
            startRate: 0,
            timeUnit: '1s',
            preAllocatedVUs: 50,
            maxVUs: 100,
            stages: [
                // Burst 1
                { duration: '10s', target: 30 },   // Ramp up to 30 RPS
                { duration: '30s', target: 30 },   // Hold at 30 RPS
                { duration: '10s', target: 0 },    // Pause

                // Burst 2
                { duration: '10s', target: 40 },   // Ramp up to 40 RPS
                { duration: '30s', target: 40 },   // Hold at 40 RPS
                { duration: '10s', target: 0 },    // Pause

                // Burst 3 (peak)
                { duration: '10s', target: 50 },   // Ramp up to 50 RPS
                { duration: '30s', target: 50 },   // Hold at 50 RPS
                { duration: '10s', target: 0 },    // Cool down
            ],
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<800', 'p(99)<1500'],
        http_req_failed: ['rate<0.02'],
        errors: ['rate<0.02'],
    },
};

// Shared test data
let testData = {
    organizationId: config.organizationId,
    leadId: null,
    conversationId: null,
};

// Setup: Create test entities before running burst test
export function setup() {
    console.log('='.repeat(60));
    console.log('  BURST TEST SETUP');
    console.log('='.repeat(60));
    console.log(`Target: ${config.baseUrl}`);
    console.log(`Organization: ${config.organizationId}`);

    const headers = getInternalHeaders();

    // Create test lead
    console.log('\n1. Creating test lead...');
    const leadPayload = createLeadPayload(config.organizationId);
    const leadRes = http.post(
        `${config.baseUrl}/internals/leads`,
        JSON.stringify(leadPayload),
        { headers }
    );

    if (leadRes.status === 201) {
        const lead = leadRes.json();
        testData.leadId = lead.id;
        console.log(`   ✓ Created lead: ${lead.id}`);
    } else {
        console.log(`   ✗ Failed to create lead: ${leadRes.status}`);
        return testData;
    }

    // Create test conversation
    console.log('2. Creating test conversation...');
    const convPayload = createConversationPayload(config.organizationId, testData.leadId);
    const convRes = http.post(
        `${config.baseUrl}/internals/conversations`,
        JSON.stringify(convPayload),
        { headers }
    );

    if (convRes.status === 201) {
        const conv = convRes.json();
        testData.conversationId = conv.id;
        console.log(`   ✓ Created conversation: ${conv.id}`);
    } else {
        console.log(`   ✗ Failed to create conversation: ${convRes.status}`);
    }

    console.log('\nSetup complete. Starting burst test...\n');
    return testData;
}

export default function (data) {
    const headers = getInternalHeaders();
    const convId = data.conversationId;
    const leadId = data.leadId;

    if (!convId || !leadId) {
        sleep(0.5);
        return;
    }

    // Simulate a user sending multiple messages in quick succession
    const messageCount = Math.floor(2 + Math.random() * 3); // 2-4 messages per burst

    for (let i = 0; i < messageCount; i++) {
        sendMessage(headers, convId, leadId);
        sleep(0.1 + Math.random() * 0.2);
    }

    // Occasional bot response
    if (Math.random() > 0.3) {
        sendBotResponse(headers, convId, leadId);
    }
}

function sendMessage(headers, convId, leadId) {
    const payload = createIncomingMessagePayload(convId, leadId);
    const url = `${config.baseUrl}/internals/messages/incoming`;

    const response = http.post(url, JSON.stringify(payload), { headers });

    const success = check(response, {
        'incoming: status 201': (r) => r.status === 201,
    });

    errorRate.add(!success);
    burstLatency.add(response.timings.duration);

    if (success) {
        messagesProcessed.add(1);
    }
}

function sendBotResponse(headers, convId, leadId) {
    const payload = createOutgoingMessagePayload(convId, leadId);
    const url = `${config.baseUrl}/internals/messages/outgoing`;

    const response = http.post(url, JSON.stringify(payload), { headers });

    const success = check(response, {
        'outgoing: status 201': (r) => r.status === 201,
    });

    errorRate.add(!success);
    burstLatency.add(response.timings.duration);

    if (success) {
        messagesProcessed.add(1);
    }
}

export function handleSummary(data) {
    const { metrics } = data;

    console.log(`
========================================
  BURST TRAFFIC TEST SUMMARY
========================================
Duration: ${(data.state.testRunDurationMs / 1000).toFixed(1)}s
Total Requests: ${metrics.http_reqs?.values?.count || 0}
Messages Processed: ${metrics.messages_processed?.values?.count || 0}
Error Rate: ${((metrics.http_req_failed?.values?.rate || 0) * 100).toFixed(2)}%

Latency:
  - p50: ${metrics.http_req_duration?.values['p(50)']?.toFixed(2) || 'N/A'}ms
  - p95: ${metrics.http_req_duration?.values['p(95)']?.toFixed(2) || 'N/A'}ms
  - p99: ${metrics.http_req_duration?.values['p(99)']?.toFixed(2) || 'N/A'}ms

Peak RPS: ${metrics.http_reqs?.values?.rate?.toFixed(2) || 'N/A'}
========================================
`);

    return {
        'loadtests/results/burst-summary.json': JSON.stringify(data, null, 2),
    };
}
