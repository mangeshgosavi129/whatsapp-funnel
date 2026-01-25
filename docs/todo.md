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








1) whatsapp worker to get tokens and other meta related data from db instead of config as different for each user

2) backend apis to be done properly

3) Frontend integration not yet complete
    a. also in the bottom left, my name should be there
    b. Add users page to list all people of the organisation

4) add Org details in settings

5) Update Backend to include user and organisation

6) Do not store anything in the session other than the token

7) Remove Pending from enums and full implementation





=====
WA W
- testing
WA R
- testing

delete whatsapp_worker/send.py file
instead implement that using the api call send_bot, send_human 

not sure about validate_signature inside the whatsapp_receive

changes
    a. lead page - update / delete / view card -- Done
    b. inbox - initially nothing selected - upon selecting a conversation, the middle section should show chats and the right side bar should show lead details -- Done
        remove assign button, tags button, display all details, remove edit button, add more details which will go to leads table specific row opened -- done
    c. whatsapp settings - if disconnected, show connect button else show disconnect button. Correct representation of state. -- Done
    d. Add user invite button which will automatically copy a link to signup with org page with org id in the link as parameter which will be preintialized -- Done
    e. update message/send in the frontend to use the api call message/send_human -- Done

    f. remove the buttons for uploading files, attachments and emojis -- done
    
    g. submit template needs multiple details to be filled, add that in each api endpoint and the frontend. 

    h. cta is not properly configured, time and name, should be the output of llm, and that should trigger the websocket event so that upon cta selection, the conversation should be shown in the actions page
    
    i. the page upon opening always keeps on leading, fix that -- Done
    
    j. restructuring the frontend to have a better structure
    k. analytics is showing incorrect values even after reloading, check for its logic, if it is correct or wrong