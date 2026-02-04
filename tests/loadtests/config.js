/**
 * k6 Load Testing Configuration
 * Target: WhatsApp Bot Server APIs (no LLM calls)
 * 
 * NOTE: These tests only hit database/API layer.
 * They do NOT send actual WhatsApp messages.
 */

export const config = {
    // Base URL for the server
    baseUrl: 'http://13.203.213.109:8000',

    // Internal API authentication
    internalSecret: 'ixfz(@FCU^Ctd6vuy1bd9cu2)uf01et7uyg',

    // Test user auth token (for external APIs)
    authToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzMjU5NjE0MC0zODBmLTQ1MzgtODFiMi00NWI5ZDRjYjZhYTYiLCJvcmdfaWQiOiJkNDgzYzgyNS1lNGViLTRjY2EtOWY5YS1lMzlkMWI4ZDNjZmQiLCJleHAiOjE3NzI3NTQzMTR9.nrJUm7kYkOgWCH53-TlpJl-r2HmduSKULxsqr1dZoM8',

    // Organization ID extracted from JWT token
    organizationId: 'd483c825-e4eb-4cca-9f9a-e39d1b8d3cfd',

    // Thresholds
    thresholds: {
        http_req_duration: ['p(95)<500', 'p(99)<1000'],
        http_req_failed: ['rate<0.01'],
    },
};

// Headers for internal API calls
export function getInternalHeaders() {
    return {
        'Content-Type': 'application/json',
        'X-Internal-Secret': config.internalSecret,
    };
}

// Headers for external API calls (user-facing)
export function getExternalHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.authToken}`,
    };
}
