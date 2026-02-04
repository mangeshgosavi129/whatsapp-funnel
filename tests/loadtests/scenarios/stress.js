/**
 * Stress Test
 * Purpose: Find system breaking points under extreme load
 * 
 * Duration: 5-10 minutes
 * VUs: Ramp to 100 concurrent users
 * Pattern: Gradual ramp up → peak → graceful ramp down
 * 
 * NOTE: This test only hits database/API layer - NO WhatsApp messages are sent.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import { config, getInternalHeaders, getExternalHeaders } from '../config.js';
import {
    createIncomingMessagePayload,
    createOutgoingMessagePayload,
    createConversationUpdatePayload,
    createLeadPayload,
    createConversationPayload,
} from '../fixtures/test-data.js';

// Custom metrics
const errorRate = new Rate('errors');
const stressLatency = new Trend('stress_latency');
const successfulOps = new Counter('successful_operations');
const failedOps = new Counter('failed_operations');

// Test configuration
export const options = {
    scenarios: {
        stress_ramp: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 50 },   // Ramp to 50 VUs
                { duration: '2m', target: 100 },  // Ramp to 100 VUs
                { duration: '3m', target: 100 },  // Hold at 100 VUs (stress period)
                { duration: '2m', target: 0 },    // Ramp down
            ],
            gracefulRampDown: '30s',
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<1500', 'p(99)<3000'],
        http_req_failed: ['rate<0.05'], // Allow up to 5% errors under stress
        errors: ['rate<0.05'],
    },
};

// Shared test data
let testData = {
    organizationId: config.organizationId,
    leadId: null,
    conversationId: null,
};

// Setup: Create test entities before stress test
export function setup() {
    console.log('='.repeat(60));
    console.log('  STRESS TEST SETUP');
    console.log('='.repeat(60));
    console.log(`Target: ${config.baseUrl}`);
    console.log(`Organization: ${config.organizationId}`);
    console.log(`Max VUs: 100`);

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
        console.log(`   ✗ Failed to create lead: ${leadRes.status} - ${leadRes.body}`);
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

    console.log('\nSetup complete. Starting stress test...\n');
    return { ...testData, startTime: Date.now() };
}

export default function (data) {
    const internalHeaders = getInternalHeaders();
    const convId = data.conversationId;
    const leadId = data.leadId;

    if (!convId || !leadId) {
        sleep(0.5);
        return;
    }

    // Mix of operations to simulate realistic load
    const operations = [
        { weight: 40, fn: () => sendIncomingMessage(internalHeaders, convId, leadId) },
        { weight: 30, fn: () => sendOutgoingMessage(internalHeaders, convId, leadId) },
        { weight: 15, fn: () => getConversation(internalHeaders, convId) },
        { weight: 10, fn: () => updateConversation(internalHeaders, convId) },
        { weight: 5, fn: () => getConversationMessages(internalHeaders, convId) },
    ];

    // Weighted random selection
    const totalWeight = operations.reduce((sum, op) => sum + op.weight, 0);
    let random = Math.random() * totalWeight;

    for (const op of operations) {
        random -= op.weight;
        if (random <= 0) {
            op.fn();
            break;
        }
    }

    // Variable think time based on VU count
    const thinkTime = Math.max(0.1, 1 - (__VU / 200));
    sleep(thinkTime + Math.random() * 0.5);
}

function sendIncomingMessage(headers, convId, leadId) {
    const payload = createIncomingMessagePayload(convId, leadId);
    const url = `${config.baseUrl}/internals/messages/incoming`;

    const response = http.post(url, JSON.stringify(payload), {
        headers,
        timeout: '10s',
    });

    recordMetrics(response, 'incoming_message');
}

function sendOutgoingMessage(headers, convId, leadId) {
    const payload = createOutgoingMessagePayload(convId, leadId);
    const url = `${config.baseUrl}/internals/messages/outgoing`;

    const response = http.post(url, JSON.stringify(payload), {
        headers,
        timeout: '10s',
    });

    recordMetrics(response, 'outgoing_message');
}

function getConversation(headers, convId) {
    const url = `${config.baseUrl}/internals/conversations/${convId}`;

    const response = http.get(url, {
        headers,
        timeout: '10s',
    });

    recordMetrics(response, 'get_conversation');
}

function updateConversation(headers, convId) {
    const payload = createConversationUpdatePayload();
    const url = `${config.baseUrl}/internals/conversations/${convId}`;

    const response = http.patch(url, JSON.stringify(payload), {
        headers,
        timeout: '10s',
    });

    recordMetrics(response, 'update_conversation');
}

function getConversationMessages(headers, convId) {
    const url = `${config.baseUrl}/internals/conversations/${convId}/messages?limit=5`;

    const response = http.get(url, {
        headers,
        timeout: '10s',
    });

    recordMetrics(response, 'get_messages');
}

function recordMetrics(response, operation) {
    const success = response.status >= 200 && response.status < 300;

    check(response, {
        [`${operation}: success`]: () => success,
    });

    if (success) {
        successfulOps.add(1);
    } else {
        failedOps.add(1);
    }

    errorRate.add(!success);
    stressLatency.add(response.timings.duration);
}

export function teardown(data) {
    const duration = (Date.now() - data.startTime) / 1000;
    console.log(`\nStress test completed in ${duration.toFixed(1)}s`);
}

export function handleSummary(data) {
    const { metrics } = data;

    const summary = `
================================================================================
                           STRESS TEST RESULTS
================================================================================

CONFIGURATION:
  Target Server: ${config.baseUrl}
  Max VUs: 100
  Duration: ${(data.state.testRunDurationMs / 1000 / 60).toFixed(1)} minutes

THROUGHPUT:
  Total Requests: ${metrics.http_reqs?.values?.count || 0}
  Requests/sec: ${metrics.http_reqs?.values?.rate?.toFixed(2) || 'N/A'}
  Successful: ${metrics.successful_operations?.values?.count || 0}
  Failed: ${metrics.failed_operations?.values?.count || 0}

LATENCY:
  Min: ${metrics.http_req_duration?.values?.min?.toFixed(2) || 'N/A'}ms
  Avg: ${metrics.http_req_duration?.values?.avg?.toFixed(2) || 'N/A'}ms
  p50: ${metrics.http_req_duration?.values['p(50)']?.toFixed(2) || 'N/A'}ms
  p90: ${metrics.http_req_duration?.values['p(90)']?.toFixed(2) || 'N/A'}ms
  p95: ${metrics.http_req_duration?.values['p(95)']?.toFixed(2) || 'N/A'}ms
  p99: ${metrics.http_req_duration?.values['p(99)']?.toFixed(2) || 'N/A'}ms
  Max: ${metrics.http_req_duration?.values?.max?.toFixed(2) || 'N/A'}ms

ERROR ANALYSIS:
  Error Rate: ${((metrics.http_req_failed?.values?.rate || 0) * 100).toFixed(2)}%

THRESHOLDS:
  p95 < 1500ms: ${(metrics.http_req_duration?.values['p(95)'] || 0) < 1500 ? 'PASS ✓' : 'FAIL ✗'}
  p99 < 3000ms: ${(metrics.http_req_duration?.values['p(99)'] || 0) < 3000 ? 'PASS ✓' : 'FAIL ✗'}
  Error < 5%: ${(metrics.http_req_failed?.values?.rate || 0) < 0.05 ? 'PASS ✓' : 'FAIL ✗'}

================================================================================
`;

    console.log(summary);

    return {
        'loadtests/results/stress-summary.json': JSON.stringify(data, null, 2),
        'loadtests/results/stress-summary.txt': summary,
    };
}
