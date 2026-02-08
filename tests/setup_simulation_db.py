import os
import sys
import psycopg2
from uuid import uuid4

# Set up connection (using env vars or default for dev)
DB_HOST = "localhost"
DB_NAME = "whatsapp_funnel"
DB_USER = "postgres"
DB_PASS = "root"

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    conn.autocommit = True
    cursor = conn.cursor()

    phone_id = "123123"

    # Check if exists
    cursor.execute("SELECT organization_id FROM whatsapp_integrations WHERE phone_number_id = %s", (phone_id,))
    result = cursor.fetchone()

    if result:
        print(f"Integration exists for Org: {result[0]}")
    else:
        print("Integration not found. Creating...")
        # Get first org
        cursor.execute("SELECT id FROM organizations LIMIT 1")
        org = cursor.fetchone()
        if not org:
            # Create org if none
            org_id = str(uuid4())
            cursor.execute("INSERT INTO organizations (id, name, business_name, business_description, flow_prompt) VALUES (%s, 'Test Org', 'Test Business', 'We sell widgets', 'Be helpful') RETURNING id", (org_id,))
            org_id = cursor.fetchone()[0]
            print(f"Created new Org: {org_id}")
        else:
            org_id = org[0]
            print(f"Using existing Org: {org_id}")

        # Create integration
        cursor.execute("""
            INSERT INTO whatsapp_integrations (id, organization_id, phone_number_id, access_token, version, app_secret)
            VALUES (%s, %s, %s, 'test_token', 'v18.0', 'test_secret')
        """, (str(uuid4()), org_id, phone_id))
        print(f"Created integration for {phone_id}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
