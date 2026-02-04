/**
 * Test Data Fixtures for k6 Load Tests
 * Generates mock payloads for API testing
 */

// Random phone number generator
export function randomPhone() {
    const prefix = '+1555';
    const suffix = Math.floor(1000000 + Math.random() * 9000000);
    return `${prefix}${suffix}`;
}

// Random message text generator
const sampleMessages = [
    "Hi, I'm interested in your services",
    "Can you tell me more about pricing?",
    "What are your business hours?",
    "I'd like to schedule a demo",
    "Thanks for the information",
    "How soon can we get started?",
    "What's included in the package?",
    "Do you offer any discounts?",
    "I have a question about the product",
    "Can I speak to a representative?",
];

export function randomMessageText() {
    return sampleMessages[Math.floor(Math.random() * sampleMessages.length)];
}

// Generate UUID v4
export function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Incoming message payload for /internals/messages/incoming
export function createIncomingMessagePayload(conversationId, leadId) {
    return {
        conversation_id: conversationId,
        lead_id: leadId,
        content: randomMessageText(),
    };
}

// Outgoing message payload for /internals/messages/outgoing
export function createOutgoingMessagePayload(conversationId, leadId) {
    return {
        conversation_id: conversationId,
        lead_id: leadId,
        content: randomMessageText(),
        message_from: 'bot',
    };
}

// Conversation update payload for /internals/conversations/{id}
// IMPORTANT: Use only valid enum values from server/enums.py
export function createConversationUpdatePayload() {
    // Valid ConversationStage values: greeting, qualification, pricing, cta, followup, closed, lost, ghosted
    const stages = ['greeting', 'qualification', 'pricing', 'cta', 'followup'];
    // Valid IntentLevel values: low, medium, high, very_high, unknown
    const intents = ['unknown', 'low', 'medium', 'high'];
    // Valid UserSentiment values: annoyed, distrustful, confused, curious, disappointed, neutral, uninterested
    const sentiments = ['neutral', 'curious', 'confused', 'disappointed'];

    return {
        stage: stages[Math.floor(Math.random() * stages.length)],
        intent_level: intents[Math.floor(Math.random() * intents.length)],
        user_sentiment: sentiments[Math.floor(Math.random() * sentiments.length)],
    };
}

// Lead creation payload for /internals/leads
export function createLeadPayload(organizationId) {
    return {
        organization_id: organizationId,
        phone: randomPhone(),
        name: `Test Lead ${Date.now()}`,
    };
}

// Conversation creation payload for /internals/conversations
export function createConversationPayload(organizationId, leadId) {
    return {
        organization_id: organizationId,
        lead_id: leadId,
    };
}
