### Server Side

## Analytics
"/" should fetch analytics for sentiment breakdown, peak activity time based on created time. Fetch that based on messages table. message_from stats which will show a pie chart on the frontend. user sentiment in bar chart, taken from conversations table. Intent level in bar chart, taken from conversations table. 

## Auth
/login should take email and password and return access token and user id and organization id. 
/signup/create-org should take name, email and password and organization name and return access token and user id and organization id. 
/signup/join-org should take name, email and password and organization id and return access token and user id and organization id. 

## Conversations
/ should get all conversations
"/{conversation_id}/messages" should get all messages for a conversation
"/{conversation_id}/takeover" should change the mode to human
"/{conversation_id}/release" should change to BOT

# send -> handled in messages

## CTAs
"/" should get all CTAs
"/" create cta based on types
"/{cta_id}" update cta 
"/{cta_id}" delete

## Dashboard
"/stats" should get all dashboard data
includes total conversations, total messages, active leads, etc.

## Leads
"/" should get all leads
"/create" this is only for testing and not for production, leads will be created from whatsapp worker.
"/{lead_id}" update lead 
"/{lead_id}" delete

## Messages
"/send" should send a message
Split send into bot and human
/send_bot, /send_human

## Organizations
"/{org_id}" should get organization details

## Settings
"/whatsapp/connect" should add whatsapp integration details, all details are important, cannot be empty
"/whatsapp/status" should get whatsapp integration status
"/whatsapp/update" should update whatsapp integration details
"/whatsapp/disconnect" should delete the whatsapp integration from the database

## Templates
"/" should get all templates
"/" should create a template
"/{template_id}" should update a template
"/{template_id}" should delete a template
"/{template_id}/submit" should submit a template for approval to meta in backend
"/{template_id}/status" should get template status and update db

## Users
"/" should get all users
"/{user_id}" should get user details
"/{user_id}" should update user details
"/{user_id}" should delete user details

## Followups
is a part of the whatsapp worker and not here, maybe use internals or something later on

## Web Sockets
"/ws" should open a web socket connection for real time updates
appropriate handling for each event and simultaneous connections to be handled.
files to be referred are server/routes/websockets.py and server/services/websocket_manager.py, server/services/websocket_events.py

authentication using token from frontend
Events include
    # Inbox
    CONVERSATION_UPDATED = "conversation:updated" => from server to frontend 
    TAKEOVER_STARTED = "conversation:takeover_started" => from frontend to server
    TAKEOVER_ENDED = "conversation:takeover_ended" => from frontend to server

    # Action Center
    ACTION_CONVERSATIONS_FLAGGED = "action:conversations_flagged" => from server to frontend
    ACTION_HUMAN_ATTENTION_REQUIRED = "action:human_attention_required" => from server to frontend

    # System
    ACK = "ack" => from server to frontend
    ERROR = "error" => from server to frontend
    SERVER_HELLO = "server:hello" => from server to frontend
    CLIENT_HEARTBEAT = "client:heartbeat" => from frontend to server

this has to be correctly initialised in the frontend and backend. 
All necessary schemas are available in the server/schemas.py file.

### Whatsapp Worker
How the whatsapp worker should work
1) long polling on aws sqs queue which contains messages from N number of customers for M number of whatsapp numbers(1 per client) 
2) For each message, 
    a) based on the receiver number[phone_number_id] (client's number not the customer's number), the worker should fetch the correct database row of all tokens and other ids - object of tokens
    b) based on the sender number, the worker should check the human in the loop logic if flag is raised or not
    switch for htl on/off
    htl on
        c) based on the sender message, the worker should run the main logic (HTL)
        d) HTL will include logic for storing the message, updating the tables, generating responses, updating enums, etc. Output will be response message
        e) Response message will be sent to the customer from the same number using the step a) fetched details
    htl off
        c)based on the sender message will be sent to frontend using websocket
        d)just respond normally like human does on whatsapp by typing
        e)send and store and websocket formality

## Whatsapp Receiver
Will need minor updates due to the new logic, can be solved using apis 

## Frontend
