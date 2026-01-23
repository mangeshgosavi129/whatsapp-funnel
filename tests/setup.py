#!/usr/bin/env python3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import and_

from server.database import SessionLocal
from server.models import Organization, Lead
from server.enums import ConversationStage, IntentLevel, UserSentiment

TEST_IDENTIFIER = "[TEST_DATA]"

TEST_LEADS = [
    {
        "name": "Sarah Johnson",
        "phone": "+12345678901",
        "email": "sarah@test.com",
        "company": "TechStart Inc."
    },
    {
        "name": "Mike Chen",
        "phone": "+12345678902",
        "email": "mike@test.com",
        "company": "Growth Labs"
    },
    {
        "name": "Emily Rodriguez",
        "phone": "+12345678903",
        "email": "emily@test.com",
        "company": "Innovation Co"
    }
]

def main():
    db: Session = SessionLocal()

    org = db.query(Organization).first()
    if not org:
        print("❌ No organization found")
        return

    print(f"♻️ Using org: {org.name}")

    existing = db.query(Lead).filter(
        and_(
            Lead.organization_id == org.id,
            Lead.company.like(f"%{TEST_IDENTIFIER}%")
        )
    ).all()

    # Remove extras
    for lead in existing[3:]:
        db.delete(lead)

    existing_phones = {l.phone for l in existing[:3]}

    for lead_data in TEST_LEADS:
        if lead_data["phone"] in existing_phones:
            continue

        lead = Lead(
            organization_id=org.id,
            name=lead_data["name"],
            phone=lead_data["phone"],
            email=lead_data["email"],
            company=f"{lead_data['company']} {TEST_IDENTIFIER}",
            conversation_stage=ConversationStage.GREETING,
            intent_level=IntentLevel.MEDIUM,
            user_sentiment=UserSentiment.NEUTRAL,
        )
        db.add(lead)
        print(f"✅ Created lead: {lead.name}")

    db.commit()
    print("🎉 Seed complete")

if __name__ == "__main__":
    main()