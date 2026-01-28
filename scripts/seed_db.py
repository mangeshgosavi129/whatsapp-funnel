import sys
import os
import uuid
from datetime import datetime
from sqlalchemy import text

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal, engine, Base
from server.models import Organization, User, Lead, Conversation, Message, WhatsAppIntegration, CTA
from server.enums import ConversationStage, IntentLevel, ConversationMode, UserSentiment, MessageFrom
from server.security import hash_password

def seed_db(clean=False):
    db = SessionLocal()
    try:
        if clean:
            print("Cleaning all data using TRUNCATE CASCADE...")
            # Using raw SQL for TRUNCATE CASCADE to handle all relationships efficiently
            tables = [
                "messages", "scheduled_actions", "conversation_events", 
                "conversations", "whatsapp_integrations", "ctas", 
                "followups", "templates", "analytics", "audit_logs", 
                "users", "leads", "organizations"
            ]
            table_string = ", ".join(tables)
            db.execute(text(f"TRUNCATE TABLE {table_string} CASCADE"))
            db.commit()
            print("Cleanup complete.")

        # Check if dummy org already exists to prevent duplicates if not cleaning
        existing_org = db.query(Organization).filter(Organization.name == "Tech Solutions Inc").first()
        if existing_org and not clean:
            print("Dummy data already seems to exist. Use --clean to recreate.")
            return

        print("Seeding dummy data...")

        # 1. Organization
        org = Organization(
            id=uuid.uuid4(),
            name="Tech Solutions Inc",
            is_active=True
        )
        db.add(org)
        db.flush() # Get IDs

        # 2. Users
        password = "password123"
        hashed_pwd = hash_password(password)
        users_data = [
            ("Admin User", "admin@techsolutions.com"),
            ("Sales Rep 1", "sales1@techsolutions.com"),
            ("Sales Rep 2", "sales2@techsolutions.com")
        ]
        users = []
        for name, email in users_data:
            u = User(
                id=uuid.uuid4(),
                organization_id=org.id,
                name=name,
                email=email,
                hashed_password=hashed_pwd,
                is_active=True
            )
            users.append(u)
            db.add(u)
        db.flush()

        # 3. WhatsApp Integration
        integration = WhatsAppIntegration(
            id=uuid.uuid4(),
            organization_id=org.id,
            access_token="EAAG...",
            version="v18.0",
            verify_token="verify_me",
            app_secret="app_secret_abc",
            phone_number_id="123456789",
            is_connected=True
        )
        db.add(integration)

        # 4. CTAs
        ctas = [
            CTA(id=uuid.uuid4(), organization_id=org.id, name="Book Demo", cta_type="book_demo"),
            CTA(id=uuid.uuid4(), organization_id=org.id, name="Book Meeting", cta_type="book_meeting")
        ]
        for cta in ctas:
            db.add(cta)
        db.flush()

        # 5. Leads
        leads_data = [
            ("John Doe", "+911234567890", "john@example.com", "Example Corp"),
            ("Jane Smith", "+919876543210", "jane@example.com", "Smith Intl"),
            ("Alice Johnson", "+915556667777", "alice@example.com", "Alice Co"),
            ("Bob Wilson", "+914443332222", "bob@example.com", "Bob Ventures"),
            ("Charlie Brown", "+918889990000", "charlie@example.com", "Peanuts Ltd")
        ]
        leads = []
        for name, phone, email, company in leads_data:
            l = Lead(
                id=uuid.uuid4(),
                organization_id=org.id,
                name=name,
                phone=phone,
                email=email,
                company=company,
                conversation_stage=ConversationStage.QUALIFICATION,
                intent_level=IntentLevel.MEDIUM,
                user_sentiment=UserSentiment.NEUTRAL
            )
            leads.append(l)
            db.add(l)
        db.flush()

        # 6. Conversations and Messages
        for lead in leads:
            for i in range(8):
                conv = Conversation(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    lead_id=lead.id,
                    stage=ConversationStage.QUALIFICATION,
                    intent_level=IntentLevel.MEDIUM,
                    mode=ConversationMode.BOT,
                    user_sentiment=UserSentiment.NEUTRAL,
                    rolling_summary=f"Conversation {i+1} with {lead.name}",
                    last_message="Hello, I'm interested"
                )
                db.add(conv)
                db.flush()

                # Messages
                m1 = Message(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    conversation_id=conv.id,
                    lead_id=lead.id,
                    message_from=MessageFrom.LEAD,
                    content="Hi, I saw your product online.",
                    status="received"
                )
                m2 = Message(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    conversation_id=conv.id,
                    lead_id=lead.id,
                    message_from=MessageFrom.BOT,
                    content="Hello! Thank you for reaching out. How can I help you today?",
                    status="sent"
                )
                m3 = Message(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    conversation_id=conv.id,
                    lead_id=lead.id,
                    message_from=MessageFrom.HUMAN,
                    assigned_user_id=users[0].id,
                    content="Let me check that for you.",
                    status="sent"
                )
                db.add_all([m1, m2, m3])

        db.commit()
        print("Seeding complete successfully!")
        
        print("\n--- Credentials ---")
        print(f"Password for all users: password123")
        for u in users:
            print(f"User: {u.name}, Email: {u.email}")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_flag = "--clean" in sys.argv
    seed_db(clean=clean_flag)
