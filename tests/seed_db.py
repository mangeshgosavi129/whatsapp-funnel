import sys
import os
from uuid import uuid4

# Add project root to path
sys.path.append(os.getcwd())

from server.database import SessionLocal
from server.models import Organization, WhatsAppIntegration

def seed_database():
    print("🌱 Seeding Database for Testing...")
    
    db = SessionLocal()
    try:
        # 1. Create Organization if needed
        org_name = "Test Org"
        org = db.query(Organization).filter(Organization.name == org_name).first()
        
        if not org:
            org = Organization(
                id=uuid4(),
                name=org_name,
                is_active=True
            )
            db.add(org)
            db.commit()
            print(f"✅ Created Organization: {org.name} ({org.id})")
        else:
            print(f"ℹ️ Organization already exists: {org.name} ({org.id})")
            
        # 2. Create WhatsApp Integration
        phone_number_id = "100609346426084" # Default test ID from simulator
        
        integration = db.query(WhatsAppIntegration).filter(
            WhatsAppIntegration.phone_number_id == phone_number_id
        ).first()
        
        if not integration:
            integration = WhatsAppIntegration(
                id=uuid4(),
                organization_id=org.id,
                access_token="mock_token",
                version="v18.0",
                verify_token="mock_verify_token",
                app_secret="mock_secret",
                phone_number_id=phone_number_id,
                is_connected=True
            )
            db.add(integration)
            db.commit()
            print(f"✅ Created WhatsApp Integration for phone ID: {phone_number_id}")
        else:
            print(f"ℹ️ Integration already exists for phone ID: {phone_number_id}")
            
        print("\n🎉 Database Seeded! You can now run 'python simulate_htl.py'")
        print(f"Use Phone Number ID: {phone_number_id}")
            
    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
