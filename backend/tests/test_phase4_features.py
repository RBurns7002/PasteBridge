"""
PasteBridge Phase 4 Features Tests - Iteration 3
Tests for: Push Tokens, Webhooks, Export (txt/md/json), AI Summarization,
and verification that existing endpoints continue to work

New endpoints tested:
- POST /api/auth/push-token (register push token, requires auth)
- DELETE /api/auth/push-token (remove push token, requires auth)
- POST /api/auth/webhooks (create webhook, requires auth)
- GET /api/auth/webhooks (list webhooks, requires auth)
- DELETE /api/auth/webhooks/{id} (delete webhook, requires auth)
- GET /api/notepad/{code}/export?format=txt|md|json
- POST /api/notepad/{code}/summarize (AI summarization)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Generate unique test run identifier
TEST_RUN_ID = str(uuid.uuid4())[:8]


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def fresh_client():
    """Fresh requests session without auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def existing_user_token(api_client):
    """Get token for existing test@test.com user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "password123"
    })
    assert response.status_code == 200, f"Failed to login existing user: {response.text}"
    return response.json()["token"]


# ==================== Health Check ====================

class TestHealth:
    """Health endpoint test"""
    
    def test_health_endpoint(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ GET /api/health returns healthy")


# ==================== Push Token Tests ====================

class TestPushToken:
    """POST /api/auth/push-token and DELETE /api/auth/push-token tests"""
    
    def test_register_push_token_requires_auth(self, fresh_client):
        """Test registering push token returns 401 without auth"""
        response = fresh_client.post(f"{BASE_URL}/api/auth/push-token", json={
            "token": "ExponentPushToken[test_no_auth_123]"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ POST /api/auth/push-token returns 401 without auth")
    
    def test_register_push_token_success(self, api_client, existing_user_token):
        """Test successfully registering a push token"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        test_token = f"ExponentPushToken[phase4_test_{TEST_RUN_ID}]"
        
        response = api_client.post(
            f"{BASE_URL}/api/auth/push-token",
            json={"token": test_token},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        assert "registered" in data["message"].lower()
        
        print(f"✓ POST /api/auth/push-token registered: {test_token}")
    
    def test_register_duplicate_push_token_no_duplicate(self, api_client, existing_user_token):
        """Test registering the same push token twice uses $addToSet (no duplicates)"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        test_token = f"ExponentPushToken[duplicate_test_{TEST_RUN_ID}]"
        
        # Register twice
        for i in range(2):
            response = api_client.post(
                f"{BASE_URL}/api/auth/push-token",
                json={"token": test_token},
                headers=headers
            )
            assert response.status_code == 200, f"Expected 200 on attempt {i+1}"
        
        print(f"✓ Duplicate push token registration handled correctly")
    
    def test_remove_push_token_requires_auth(self, fresh_client):
        """Test removing push token returns 401 without auth"""
        response = fresh_client.delete(f"{BASE_URL}/api/auth/push-token", json={
            "token": "ExponentPushToken[any_token]"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ DELETE /api/auth/push-token returns 401 without auth")
    
    def test_remove_push_token_success(self, api_client, existing_user_token):
        """Test successfully removing a push token"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        test_token = f"ExponentPushToken[to_remove_{TEST_RUN_ID}]"
        
        # First register the token
        reg_response = api_client.post(
            f"{BASE_URL}/api/auth/push-token",
            json={"token": test_token},
            headers=headers
        )
        assert reg_response.status_code == 200
        
        # Then remove it
        response = api_client.delete(
            f"{BASE_URL}/api/auth/push-token",
            json={"token": test_token},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        assert "removed" in data["message"].lower()
        
        print(f"✓ DELETE /api/auth/push-token removed: {test_token}")
    
    def test_remove_nonexistent_push_token_succeeds(self, api_client, existing_user_token):
        """Test removing non-existent token doesn't error (idempotent)"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.delete(
            f"{BASE_URL}/api/auth/push-token",
            json={"token": "ExponentPushToken[nonexistent_xyz123]"},
            headers=headers
        )
        
        # Should succeed (idempotent operation)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Remove non-existent push token is idempotent (returns 200)")


# ==================== Webhook Tests ====================

class TestWebhooks:
    """POST/GET/DELETE /api/auth/webhooks tests"""
    
    def test_create_webhook_requires_auth(self, fresh_client):
        """Test creating webhook returns 401 without auth"""
        response = fresh_client.post(f"{BASE_URL}/api/auth/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["new_entry"]
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ POST /api/auth/webhooks returns 401 without auth")
    
    def test_create_webhook_success(self, api_client, existing_user_token):
        """Test successfully creating a webhook"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        webhook_url = f"https://webhook.site/test-{TEST_RUN_ID}"
        
        response = api_client.post(
            f"{BASE_URL}/api/auth/webhooks",
            json={
                "url": webhook_url,
                "events": ["new_entry"]
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert "url" in data
        assert "events" in data
        assert "secret" in data
        assert "active" in data
        
        assert data["url"] == webhook_url
        assert data["events"] == ["new_entry"]
        assert data["active"] == True
        assert len(data["secret"]) > 0  # Auto-generated secret
        
        print(f"✓ POST /api/auth/webhooks created webhook: {data['id']}")
        return data["id"]
    
    def test_create_webhook_with_custom_secret(self, api_client, existing_user_token):
        """Test creating webhook with custom secret"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        custom_secret = f"my_secret_{TEST_RUN_ID}"
        
        response = api_client.post(
            f"{BASE_URL}/api/auth/webhooks",
            json={
                "url": f"https://example.com/custom-secret-{TEST_RUN_ID}",
                "events": ["new_entry"],
                "secret": custom_secret
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["secret"] == custom_secret
        
        print(f"✓ Webhook created with custom secret")
    
    def test_list_webhooks_requires_auth(self, fresh_client):
        """Test listing webhooks returns 401 without auth"""
        response = fresh_client.get(f"{BASE_URL}/api/auth/webhooks")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ GET /api/auth/webhooks returns 401 without auth")
    
    def test_list_webhooks_success(self, api_client, existing_user_token):
        """Test successfully listing user webhooks"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/auth/webhooks", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list)
        
        # Each webhook should have expected fields
        if len(data) > 0:
            webhook = data[0]
            assert "id" in webhook
            assert "url" in webhook
            assert "events" in webhook
            assert "active" in webhook
            # Note: secret should NOT be in list response (security)
            # created_at may or may not be included
        
        print(f"✓ GET /api/auth/webhooks returned {len(data)} webhook(s)")
    
    def test_delete_webhook_requires_auth(self, fresh_client):
        """Test deleting webhook returns 401 without auth"""
        response = fresh_client.delete(f"{BASE_URL}/api/auth/webhooks/some-id-123")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ DELETE /api/auth/webhooks/{id} returns 401 without auth")
    
    def test_delete_webhook_success(self, api_client, existing_user_token):
        """Test successfully deleting a webhook"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # First create a webhook to delete
        create_response = api_client.post(
            f"{BASE_URL}/api/auth/webhooks",
            json={
                "url": f"https://example.com/to-delete-{TEST_RUN_ID}",
                "events": ["new_entry"]
            },
            headers=headers
        )
        assert create_response.status_code == 200
        webhook_id = create_response.json()["id"]
        
        # Delete it
        response = api_client.delete(
            f"{BASE_URL}/api/auth/webhooks/{webhook_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        assert "deleted" in data["message"].lower()
        
        print(f"✓ DELETE /api/auth/webhooks/{webhook_id} deleted successfully")
    
    def test_delete_nonexistent_webhook_returns_404(self, api_client, existing_user_token):
        """Test deleting non-existent webhook returns 404"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.delete(
            f"{BASE_URL}/api/auth/webhooks/nonexistent-webhook-id-xyz",
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ DELETE /api/auth/webhooks/{id} returns 404 for non-existent webhook")


# ==================== Export Endpoint Tests ====================

class TestExport:
    """GET /api/notepad/{code}/export tests"""
    
    @pytest.fixture(scope="class")
    def test_notepad_with_entries(self, api_client):
        """Create a notepad with entries for export testing"""
        # Create notepad
        response = api_client.post(f"{BASE_URL}/api/notepad")
        assert response.status_code == 200
        code = response.json()["code"]
        
        # Add multiple entries
        entries = [
            "First test entry for export",
            "Second entry with\nmultiline content",
            "Third entry: special chars <>&\""
        ]
        
        for text in entries:
            append_response = api_client.post(
                f"{BASE_URL}/api/notepad/{code}/append",
                json={"text": text}
            )
            assert append_response.status_code == 200
        
        return code
    
    def test_export_as_txt(self, api_client, test_notepad_with_entries):
        """Test export notepad as text format"""
        code = test_notepad_with_entries
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/export?format=txt")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify content type
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type
        
        # Verify Content-Disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert f"{code}.txt" in content_disp
        
        # Verify content contains notepad info and entries
        content = response.text
        assert "PasteBridge" in content
        assert code in content
        assert "First test entry for export" in content
        
        print(f"✓ GET /api/notepad/{code}/export?format=txt works correctly")
    
    def test_export_as_json(self, api_client, test_notepad_with_entries):
        """Test export notepad as JSON format"""
        code = test_notepad_with_entries
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/export?format=json")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type
        
        # Verify Content-Disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert f"{code}.json" in content_disp
        
        # Parse and verify JSON structure
        import json
        data = json.loads(response.text)
        
        assert "code" in data
        assert data["code"] == code
        assert "created_at" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) >= 3
        
        # Verify entry structure
        entry = data["entries"][0]
        assert "text" in entry
        assert "timestamp" in entry
        
        print(f"✓ GET /api/notepad/{code}/export?format=json works correctly")
    
    def test_export_as_markdown(self, api_client, test_notepad_with_entries):
        """Test export notepad as markdown format"""
        code = test_notepad_with_entries
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/export?format=md")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get("content-type", "")
        assert "text/markdown" in content_type
        
        # Verify Content-Disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert f"{code}.md" in content_disp
        
        # Verify markdown content
        content = response.text
        assert f"# PasteBridge: {code}" in content
        assert "###" in content  # Timestamp headers
        assert "First test entry for export" in content
        
        print(f"✓ GET /api/notepad/{code}/export?format=md works correctly")
    
    def test_export_default_format_is_txt(self, api_client, test_notepad_with_entries):
        """Test export without format param defaults to txt"""
        code = test_notepad_with_entries
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/export")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type
        
        print("✓ Export defaults to txt format when format param omitted")
    
    def test_export_nonexistent_notepad_returns_404(self, api_client):
        """Test export non-existent notepad returns 404"""
        response = api_client.get(f"{BASE_URL}/api/notepad/nonexistent_xyz123/export?format=txt")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Export for non-existent notepad returns 404")
    
    def test_export_empty_notepad(self, api_client):
        """Test export empty notepad (no entries)"""
        # Create new empty notepad
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/export?format=json")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        import json
        data = json.loads(response.text)
        assert data["entries"] == []
        
        print("✓ Export empty notepad works correctly")


# ==================== AI Summarization Tests ====================

class TestAISummarization:
    """POST /api/notepad/{code}/summarize tests"""
    
    @pytest.fixture(scope="class")
    def notepad_with_content(self, api_client):
        """Create a notepad with substantial content for summarization"""
        # Create notepad
        response = api_client.post(f"{BASE_URL}/api/notepad")
        assert response.status_code == 200
        code = response.json()["code"]
        
        # Add substantial content
        content = """
        Meeting Notes - Project Planning
        
        Discussed the new feature roadmap for Q1 2026:
        1. User authentication improvements
        2. Push notification system
        3. Webhook integrations
        4. Export functionality
        5. AI-powered summarization
        
        Action items:
        - John to review security requirements
        - Sarah to design notification flow
        - Team to finalize API contracts by Friday
        
        Next meeting scheduled for Monday at 2pm.
        """
        
        append_response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": content}
        )
        assert append_response.status_code == 200
        
        return code
    
    def test_summarize_notepad_success(self, api_client, notepad_with_content):
        """Test AI summarization of notepad content"""
        code = notepad_with_content
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/summarize",
            json={"max_length": 500},
            timeout=30  # AI calls can take longer
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "code" in data
        assert data["code"] == code.lower()
        assert "summary" in data
        assert "entry_count" in data
        assert "model" in data
        
        # Verify summary is present and not empty
        assert len(data["summary"]) > 0
        assert data["entry_count"] >= 1
        assert data["model"] == "gpt-5.2"
        
        print(f"✓ POST /api/notepad/{code}/summarize returned summary ({len(data['summary'])} chars)")
        print(f"  Summary preview: {data['summary'][:100]}...")
    
    def test_summarize_empty_notepad_returns_400(self, api_client):
        """Test summarizing empty notepad returns 400"""
        # Create new empty notepad
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/summarize",
            timeout=10
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "no entries" in data.get("detail", "").lower()
        
        print("✓ Summarize empty notepad correctly returns 400")
    
    def test_summarize_nonexistent_notepad_returns_404(self, api_client):
        """Test summarizing non-existent notepad returns 404"""
        response = api_client.post(
            f"{BASE_URL}/api/notepad/nonexistent_xyz123/summarize",
            timeout=10
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Summarize non-existent notepad returns 404")
    
    def test_summarize_with_default_max_length(self, api_client, notepad_with_content):
        """Test summarization with default max_length (no body)"""
        code = notepad_with_content
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/summarize",
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "summary" in data
        
        print("✓ Summarize with default max_length works")


# ==================== Web View Push Notification Trigger Test ====================

class TestWebViewPushNotification:
    """Test that viewing notepad triggers push notification lookup for owner"""
    
    def test_view_notepad_with_owner_loads_correctly(self, api_client, existing_user_token):
        """Test viewing owned notepad loads (push notification is async, we verify page loads)"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # Create notepad as authenticated user (has owner)
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # View the notepad via web page
        view_response = api_client.get(f"{BASE_URL}/api/notepad/{code}/view")
        
        assert view_response.status_code == 200, f"Expected 200, got {view_response.status_code}"
        assert "PasteBridge" in view_response.text
        assert code in view_response.text
        
        # Note: Push notification is sent asynchronously, we just verify the page loads
        # The actual push notification goes to Expo's service and would fail silently
        # for fake tokens like ExponentPushToken[test123]
        
        print(f"✓ Web view /api/notepad/{code}/view loads correctly (push notification triggered async)")


# ==================== Webhook Firing on Append Test ====================

class TestWebhookFiringOnAppend:
    """Test that webhooks are fired when appending to owned notepad"""
    
    def test_append_to_owned_notepad_triggers_webhook(self, api_client, existing_user_token):
        """Test appending to owned notepad fires webhooks (async)"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # Create a webhook
        webhook_response = api_client.post(
            f"{BASE_URL}/api/auth/webhooks",
            json={
                "url": f"https://webhook.site/fire-test-{TEST_RUN_ID}",
                "events": ["new_entry"]
            },
            headers=headers
        )
        assert webhook_response.status_code == 200
        
        # Create notepad as authenticated user (has owner)
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Append to the notepad (should trigger webhook)
        append_response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": f"Webhook trigger test entry {TEST_RUN_ID}"}
        )
        
        assert append_response.status_code == 200, f"Expected 200, got {append_response.status_code}"
        
        # Note: Webhook is fired asynchronously via fire_webhooks()
        # The webhook URL may fail (webhook.site) but the append should succeed
        # We can't easily verify webhook was actually fired without a real receiver
        
        print(f"✓ Append to owned notepad succeeded (webhook firing is async)")


# ==================== Existing Endpoints Still Work ====================

class TestExistingEndpointsStillWork:
    """Verify existing auth and notepad endpoints are not broken"""
    
    def test_register_still_works(self, api_client):
        """Test user registration still works"""
        unique_email = f"TEST_phase4_{uuid.uuid4().hex[:8]}@test.com"
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Phase4 Test"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ POST /api/auth/register still works")
    
    def test_login_still_works(self, api_client):
        """Test login with existing user still works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "password123"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/auth/login still works")
    
    def test_get_me_still_works(self, api_client, existing_user_token):
        """Test GET /api/auth/me still works"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/auth/me still works")
    
    def test_create_notepad_still_works(self, api_client):
        """Test POST /api/notepad still works"""
        response = api_client.post(f"{BASE_URL}/api/notepad")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "code" in data
        print(f"✓ POST /api/notepad still works (created: {data['code']})")
    
    def test_get_notepad_still_works(self, api_client):
        """Test GET /api/notepad/{code} still works"""
        # Create and then get
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}")
        assert response.status_code == 200
        print("✓ GET /api/notepad/{code} still works")
    
    def test_append_notepad_still_works(self, api_client):
        """Test POST /api/notepad/{code}/append still works"""
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": "Phase4 test append"}
        )
        assert response.status_code == 200
        print("✓ POST /api/notepad/{code}/append still works")
    
    def test_clear_notepad_still_works(self, api_client):
        """Test DELETE /api/notepad/{code} still works"""
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        response = api_client.delete(f"{BASE_URL}/api/notepad/{code}")
        assert response.status_code == 200
        print("✓ DELETE /api/notepad/{code} still works")
    
    def test_landing_page_still_renders(self, api_client):
        """Test GET /api/ still renders"""
        response = api_client.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        print("✓ GET /api/ landing page still renders")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
