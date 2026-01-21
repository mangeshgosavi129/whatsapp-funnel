import requests
import json
from uuid import UUID

BASE_URL = "http://127.0.0.1:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0NjcxZjI4YS01YjAyLTQ1OTctYjQ3YS05Yzc3MTRlZmEwNTgiLCJvcmdfaWQiOiI5NzRmOTI4OC0zZTA1LTRjMDAtYjczOC1jOWFjMzliYjQxNjkiLCJleHAiOjE3NzE1OTcwMjh9.Mr-Z45bM9TR-hezrrSjMhrpRPR7x-NSy0b7fe_q1Ddw"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def print_result(endpoint, status, response_text):
    print(f"\n📍 Endpoint: {endpoint}")
    print(f"✅ Status: {status}" if 200 <= status < 300 else f"❌ Status: {status}")
    try:
        response_json = json.loads(response_text)
        print(f"📦 Response: {json.dumps(response_json, indent=2)}")
        return response_json
    except:
        print(f"📦 Response: {response_text}")
        return None

def test_users():
    print("\n" + "="*60)
    print("  USER API TESTS")
    print("="*60)

    # 1. Get all users
    print("\n👥 Testing Get All Users...")
    response = requests.get(f"{BASE_URL}/users/", headers=headers)
    users = print_result("GET /users/", response.status_code, response.text)

    if response.status_code == 200 and users:
        # Get details for the first user
        user_id = users[0].get("id")
        
        # 2. Get user by ID
        print(f"\n👤 Testing Get User by ID ({user_id})...")
        response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers)
        print_result(f"GET /users/{user_id}", response.status_code, response.text)

        # 3. Update user
        print(f"\n✏️ Testing Update User ({user_id})...")
        old_name = users[0].get("name")
        update_payload = {"name": f"{old_name} (Updated)"}
        response = requests.patch(f"{BASE_URL}/users/{user_id}", headers=headers, json=update_payload)
        print_result(f"PATCH /users/{user_id}", response.status_code, response.text)

        # 4. Verify update (optional, but good)
        print(f"\n🔍 Verifying Update...")
        response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers)
        updated_user = print_result(f"GET /users/{user_id}", response.status_code, response.text)
        
        # Revert change to keep data clean
        print(f"\n🔄 Reverting Name Change...")
        requests.patch(f"{BASE_URL}/users/{user_id}", headers=headers, json={"name": old_name})

        # 5. Delete user (WARNING: This will fail if we try to delete ourselves or if there's only one user)
        # We skip actual deletion for safety unless we create a temporary user.
        print("\n🗑️ Testing Delete User (Skipped for safety in this script)...")
        # To test delete, you'd need a temp user or a safe user ID.
        # response = requests.delete(f"{BASE_URL}/users/{user_id}", headers=headers)
        # print_result(f"DELETE /users/{user_id}", response.status_code, response.text)

if __name__ == "__main__":
    test_users()
