ConversationStage
    1.greeting
    2.qualification
    3.pricing
    4.cta
    5.followup
    6.closed
    7.lost
    8.ghosted

Intent
    1. low
    2. medium
    3. high
    4. very high
    5. unknown

CTA type
    1. book a call
    2. book a demo
    3. book a meeting
    4. send link

Modes
    1. Bot
    2. Human
    3. Closed
    4. Paused

UserSentiment
    1. Annoyed
    2. Distrustful
    3. Confused
    4. Curious
    5. Disappointed
    6. Neutral
    7. Uninterested


1. Dashboard
	Get basic stats
        GET /dashboard/stats
            -> Usage: display general stats

2. Actions (WebSocket)
	REST
	•	GET /ctas
            -> Usage: Get all CTAs
	•	POST /ctas
            -> Usage: Create a CTA
    •	PUT /ctas/{cta_id}
            -> Usage: Update a CTA, including on/off, phone number, etc.
    •	DELETE /ctas/{cta_id}
            -> Usage: Delete a CTA
    WebSocket
    •   action:conversations_flagged
            -> Usage: all cta accepted conversations will be displayed in the action center
    •   action:human_attention_required
            -> Usage: Request takeover from bot to human

3. Inbox
	REST
	•	GET /conversations
	•	GET /conversations/{conversation_id}/messages
	•	POST /messages/send
	•	POST /conversations/{conversation_id}/takeover
	•	POST /conversations/{conversation_id}/release
    WebSocket
	•	message:received
	•	message:sent
	•	conversation:updated
	•	conversation:takeover_started
	•	conversation:takeover_ended

4.  Templates
    REST
	•	POST /templates
            -> Usage: create template, including when to send this message
	•	GET /templates
            -> Usage: get templates
	•	PUT /templates/{template_id}
            -> Usage: update template
	•	DELETE /templates/{template_id}
            -> Usage: delete template
	•	POST /templates/{template_id}/submit
            -> Usage: submit template
	•	GET /templates/{template_id}/status
            -> Usage: get template status

5. Leads
    •	GET /leads
            -> Usage: get leads
	•	PUT /leads/{lead_id}
            -> Usage: update lead
	•	DELETE /leads/{lead_id}
            -> Usage: delete lead

6. Analytics
    GET /analytics
        Peak activity hour wise
        lead sources
        conversation volume
        sentiment

7. Settings
    •	POST /settings/whatsapp/connect
    •	GET /settings/whatsapp/status
    •	PUT /settings/whatsapp/config
    •	DELETE /settings/whatsapp/disconnect


========================================

Core
	•	organizations
	•	users

Inbox / Conversations
	•	conversations
	•	messages

CTAs / Actions
	•	ctas
	•	cta_conversations ( not sure about this, just have correct column in conversations )

Templates
	•	templates
	•	template_approvals ( not sure about this , just have a status column in templates )

Leads
	•	leads

Analytics
	•	conversation_metrics 
	•	sentiment_metrics

Settings / Integrations
	•	whatsapp_integrations

System / Infra
	•	audit_logs



Add users page to list all people of the organisation
add Org details in settings
also in the bottom left, my name should be there
backend apis to be done properly
