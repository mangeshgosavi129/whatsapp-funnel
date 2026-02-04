/**
 * Baseline Load Test
 * Purpose: Validate system stability under normal load
 * 
 * Duration: 10-15 minutes
 * Rate: ~1 request/second
 * VUs: 1-5
 * 
 * NOTE: This test only hits database/API layer - NO WhatsApp messages are sent.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
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
const internalApiDuration = new Trend('internal_api_duration');
const externalApiDuration = new Trend('external_api_duration');

// Test configuration
export const options = {
    scenarios: {
        baseline: {
            executor: 'constant-arrival-rate',
            rate: 1,              // 1 request per second
            timeUnit: '1s',
            duration: '10m',      // 10 minutes
            preAllocatedVUs: 5,
            maxVUs: 10,
        },
    },
    thresholds: {
        http_req_duration: ['p(95)<500', 'p(99)<1000'],
        http_req_failed: ['rate<0.05'],  // Allow some 404s during setup
        errors: ['rate<0.05'],
    },
};

// Shared test data - populated in setup()
let testData = {
    organizationId: config.organizationId,
    leadId: null,
    conversationId: null,
};

// Setup: Create test lead and conversation before running tests
export function setup() {
    console.log('='.repeat(60));
    console.log('  BASELINE TEST SETUP');
    console.log('='.repeat(60));
    console.log(`Target: ${config.baseUrl}`);
    console.log(`Organization: ${config.organizationId}`);

    const headers = getInternalHeaders();

    // Step 1: Create a test lead
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

    // Step 2: Create a test conversation
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
        console.log(`   ✗ Failed to create conversation: ${convRes.status} - ${convRes.body}`);
    }

    console.log('\nSetup complete. Starting load test...\n');
    return testData;
}

export default function (data) {
    const internalHeaders = getInternalHeaders();
    const externalHeaders = getExternalHeaders();

    // Use the test data created in setup
    const convId = data.conversationId;
    const leadId = data.leadId;

    if (!convId || !leadId) {
        console.log('Warning: Missing test data, skipping iteration');
        sleep(1);
        return;
    }

    // Randomly select an endpoint to test
    const testChoice = Math.random();

    if (testChoice < 0.3) {
        testIncomingMessage(internalHeaders, convId, leadId);
    } else if (testChoice < 0.6) {
        testOutgoingMessage(internalHeaders, convId, leadId);
    } else if (testChoice < 0.75) {
        testGetConversation(internalHeaders, convId);
    } else if (testChoice < 0.9) {
        testUpdateConversation(internalHeaders, convId);
    } else {
        testExternalConversations(externalHeaders);
    }

    // Small delay between requests
    sleep(0.5 + Math.random() * 0.5);
}

function testIncomingMessage(headers, convId, leadId) {
    const payload = createIncomingMessagePayload(convId, leadId);
    const url = `${config.baseUrl}/internals/messages/incoming`;

    const response = http.post(url, JSON.stringify(payload), { headers });

    const success = check(response, {
        'incoming message: status is 201': (r) => r.status === 201,
    });

    errorRate.add(!success);
    internalApiDuration.add(response.timings.duration);
}

function testOutgoingMessage(headers, convId, leadId) {
    const payload = createOutgoingMessagePayload(convId, leadId);
    const url = `${config.baseUrl}/internals/messages/outgoing`;

    const response = http.post(url, JSON.stringify(payload), { headers });

    const success = check(response, {
        'outgoing message: status is 201': (r) => r.status === 201,
    });

    errorRate.add(!success);
    internalApiDuration.add(response.timings.duration);
}

function testGetConversation(headers, convId) {
    const url = `${config.baseUrl}/internals/conversations/${convId}`;

    const response = http.get(url, { headers });

    const success = check(response, {
        'get conversation: status is 200': (r) => r.status === 200,
    });

    errorRate.add(!success);
    internalApiDuration.add(response.timings.duration);
}

function testUpdateConversation(headers, convId) {
    const payload = createConversationUpdatePayload();
    const url = `${config.baseUrl}/internals/conversations/${convId}`;

    const response = http.patch(url, JSON.stringify(payload), { headers });

    const success = check(response, {
        'update conversation: status is 200': (r) => r.status === 200,
    });

    errorRate.add(!success);
    internalApiDuration.add(response.timings.duration);
}

function testExternalConversations(headers) {
    const url = `${config.baseUrl}/conversations/`;

    const response = http.get(url, { headers });

    const success = check(response, {
        'external conversations: status is 200': (r) => r.status === 200,
    });

    errorRate.add(!success);
    externalApiDuration.add(response.timings.duration);
}

export function handleSummary(data) {
    const { metrics } = data;

    const summary = `
========================================
  BASELINE TEST SUMMARY
========================================
Duration: ${(data.state.testRunDurationMs / 1000).toFixed(1)}s
Total Requests: ${metrics.http_reqs?.values?.count || 0}
Error Rate: ${((metrics.http_req_failed?.values?.rate || 0) * 100).toFixed(2)}%

Latency:
  - p50: ${metrics.http_req_duration?.values['p(50)']?.toFixed(2) || 'N/A'}ms
  - p95: ${metrics.http_req_duration?.values['p(95)']?.toFixed(2) || 'N/A'}ms
  - p99: ${metrics.http_req_duration?.values['p(99)']?.toFixed(2) || 'N/A'}ms
========================================
`;
    console.log(summary);

    return {
        'loadtests/results/baseline-summary.json': JSON.stringify(data, null, 2),
    };
}
