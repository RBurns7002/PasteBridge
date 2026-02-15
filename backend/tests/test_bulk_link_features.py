"""
PasteBridge Bulk Link Features Tests - Iteration 2
Tests for: POST /api/auth/link-notepads (bulk link), authenticated notepad creation,
and verification that existing endpoints continue to work
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Generate unique test email for each test run
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


@pytest.fixture(scope="module")
def new_test_user_credentials():
    """Generate unique credentials for new test user"""
    return {
        "email": f"TEST_bulk_{TEST_RUN_ID}@test.com",
        "password": "testbulk123",
        "name": "Bulk Test User"
    }


@pytest.fixture(scope="module")
def new_user_token(api_client, new_test_user_credentials):
    """Register a new test user and return token"""
    response = api_client.post(f"{BASE_URL}/api/auth/register", json=new_test_user_credentials)
    assert response.status_code == 200, f"Failed to register new test user: {response.text}"
    return response.json()["token"]


# ==================== Bulk Link Endpoint Tests ====================

class TestBulkLinkNotepads:
    """POST /api/auth/link-notepads tests - NEW bulk link feature"""
    
    def test_bulk_link_rejects_without_auth(self, fresh_client):
        """Test bulk link returns 401 without authentication"""
        response = fresh_client.post(f"{BASE_URL}/api/auth/link-notepads", json={
            "codes": ["testcode1", "testcode2"]
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ POST /api/auth/link-notepads returns 401 without auth")
    
    def test_bulk_link_handles_nonexistent_codes(self, api_client, existing_user_token):
        """Test bulk link handles non-existent codes gracefully (skips them)"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        nonexistent_codes = [
            f"nonexistent_{uuid.uuid4().hex[:8]}",
            f"fake_code_{uuid.uuid4().hex[:8]}",
            f"missing_{uuid.uuid4().hex[:8]}"
        ]
        
        response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": nonexistent_codes},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "linked_count" in data
        assert "skipped_count" in data
        assert "linked" in data
        assert "skipped" in data
        
        # All codes should be skipped as not found
        assert data["linked_count"] == 0
        assert data["skipped_count"] == len(nonexistent_codes)
        
        # Verify skipped reasons
        for skipped in data["skipped"]:
            assert skipped["reason"] == "not found"
        
        print(f"✓ Bulk link handles {len(nonexistent_codes)} non-existent codes gracefully")
    
    def test_bulk_link_multiple_guest_notepads(self, fresh_client, api_client, new_user_token):
        """Test successfully bulk linking multiple guest notepads to user"""
        headers = {"Authorization": f"Bearer {new_user_token}"}
        
        # Create multiple guest notepads (without auth)
        guest_codes = []
        for i in range(3):
            response = fresh_client.post(f"{BASE_URL}/api/notepad")
            assert response.status_code == 200, f"Failed to create guest notepad {i}"
            guest_codes.append(response.json()["code"])
            # Verify they are guest notepads
            assert response.json()["account_type"] == "guest"
            assert response.json().get("user_id") is None
        
        print(f"Created guest notepads: {guest_codes}")
        
        # Bulk link all guest notepads to user
        link_response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": guest_codes},
            headers=headers
        )
        
        assert link_response.status_code == 200, f"Expected 200, got {link_response.status_code}: {link_response.text}"
        data = link_response.json()
        
        # Verify all linked successfully
        assert data["linked_count"] == 3, f"Expected 3 linked, got {data['linked_count']}"
        assert data["skipped_count"] == 0
        assert len(data["linked"]) == 3
        
        # Verify codes are in linked list
        for code in guest_codes:
            assert code.lower() in data["linked"]
        
        # Verify notepads are now linked to user via GET /api/auth/notepads
        notepads_response = api_client.get(f"{BASE_URL}/api/auth/notepads", headers=headers)
        assert notepads_response.status_code == 200
        user_notepads = notepads_response.json()
        user_codes = [n["code"] for n in user_notepads]
        
        for code in guest_codes:
            assert code.lower() in user_codes, f"Code {code} not found in user's notepads"
        
        print(f"✓ Successfully bulk linked {len(guest_codes)} guest notepads")
    
    def test_bulk_link_skips_already_linked_notepads(self, api_client, new_user_token):
        """Test bulk link skips notepads already linked to same user"""
        headers = {"Authorization": f"Bearer {new_user_token}"}
        
        # Create a notepad with auth (already linked to user)
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        linked_code = create_response.json()["code"]
        
        # Try to bulk link the already-linked notepad
        response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": [linked_code]},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["linked_count"] == 0
        assert data["skipped_count"] == 1
        
        # Verify reason is "already yours"
        assert data["skipped"][0]["code"] == linked_code.lower()
        assert data["skipped"][0]["reason"] == "already yours"
        
        print(f"✓ Bulk link correctly skips already-linked notepad {linked_code}")
    
    def test_bulk_link_mixed_codes(self, fresh_client, api_client, new_user_token):
        """Test bulk link with mix of valid, invalid, and already-linked codes"""
        headers = {"Authorization": f"Bearer {new_user_token}"}
        
        # Create one guest notepad
        guest_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert guest_response.status_code == 200
        guest_code = guest_response.json()["code"]
        
        # Create one user notepad (already linked)
        user_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert user_response.status_code == 200
        user_code = user_response.json()["code"]
        
        # Mix of codes
        nonexistent_code = f"nonexistent_{uuid.uuid4().hex[:8]}"
        mixed_codes = [guest_code, user_code, nonexistent_code]
        
        # Bulk link
        response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": mixed_codes},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should link 1 (guest), skip 2 (already yours + not found)
        assert data["linked_count"] == 1
        assert data["skipped_count"] == 2
        assert guest_code.lower() in data["linked"]
        
        # Verify skip reasons
        skip_reasons = {s["code"]: s["reason"] for s in data["skipped"]}
        assert skip_reasons[user_code.lower()] == "already yours"
        assert skip_reasons[nonexistent_code.lower()] == "not found"
        
        print("✓ Bulk link handles mixed codes correctly")
    
    def test_bulk_link_skips_notepad_belonging_to_another_user(self, fresh_client, api_client, existing_user_token, new_user_token):
        """Test bulk link skips notepads belonging to another user"""
        headers_existing = {"Authorization": f"Bearer {existing_user_token}"}
        headers_new = {"Authorization": f"Bearer {new_user_token}"}
        
        # Create notepad linked to existing user
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers_existing)
        assert create_response.status_code == 200
        other_user_code = create_response.json()["code"]
        
        # Try to bulk link to new user
        response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": [other_user_code]},
            headers=headers_new
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["linked_count"] == 0
        assert data["skipped_count"] == 1
        assert data["skipped"][0]["reason"] == "belongs to another user"
        
        print("✓ Bulk link correctly skips notepad belonging to another user")
    
    def test_bulk_link_empty_array(self, api_client, existing_user_token):
        """Test bulk link with empty codes array"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": []},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["linked_count"] == 0
        assert data["skipped_count"] == 0
        
        print("✓ Bulk link handles empty codes array correctly")


# ==================== Notepad Creation Tests ====================

class TestNotepadCreationUserLinking:
    """POST /api/notepad - verify user_id linking and account_type"""
    
    def test_guest_notepad_has_null_user_id_and_guest_account_type(self, fresh_client):
        """Test guest notepad creation has user_id=null and account_type=guest"""
        response = fresh_client.post(f"{BASE_URL}/api/notepad")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get("user_id") is None, f"Expected user_id=null, got {data.get('user_id')}"
        assert data["account_type"] == "guest", f"Expected account_type=guest, got {data['account_type']}"
        
        # Verify expiration is ~90 days (guest)
        assert data.get("expires_at") is not None
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        days_diff = (expires_at.replace(tzinfo=None) - datetime.utcnow()).days
        assert 85 <= days_diff <= 95, f"Expected ~90 days expiration for guest, got {days_diff}"
        
        print(f"✓ Guest notepad created: user_id=null, account_type=guest, expires in ~{days_diff} days")
    
    def test_authenticated_notepad_has_user_id_and_user_account_type(self, api_client, existing_user_token):
        """Test authenticated notepad creation has user_id set and account_type=user"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # Get user info first
        me_response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        user_id = me_response.json()["id"]
        
        # Create notepad with auth
        response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify user_id is set
        assert data.get("user_id") is not None, "Expected user_id to be set"
        assert data["user_id"] == user_id, f"Expected user_id={user_id}, got {data['user_id']}"
        
        # Verify account_type is user
        assert data["account_type"] == "user", f"Expected account_type=user, got {data['account_type']}"
        
        # Verify expiration is ~365 days (user)
        assert data.get("expires_at") is not None
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        days_diff = (expires_at.replace(tzinfo=None) - datetime.utcnow()).days
        assert 360 <= days_diff <= 370, f"Expected ~365 days expiration for user, got {days_diff}"
        
        print(f"✓ Authenticated notepad created: user_id={user_id}, account_type=user, expires in ~{days_diff} days")


# ==================== GET User Notepads Tests ====================

class TestGetUserNotepads:
    """GET /api/auth/notepads - verify user notepads retrieval after bulk link"""
    
    def test_get_user_notepads_includes_bulk_linked(self, fresh_client, api_client, existing_user_token):
        """Test GET /api/auth/notepads returns bulk-linked notepads"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # Get initial notepad count
        initial_response = api_client.get(f"{BASE_URL}/api/auth/notepads", headers=headers)
        assert initial_response.status_code == 200
        initial_count = len(initial_response.json())
        
        # Create a guest notepad
        guest_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert guest_response.status_code == 200
        guest_code = guest_response.json()["code"]
        
        # Bulk link it
        link_response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepads",
            json={"codes": [guest_code]},
            headers=headers
        )
        assert link_response.status_code == 200
        assert link_response.json()["linked_count"] == 1
        
        # Get user notepads again
        final_response = api_client.get(f"{BASE_URL}/api/auth/notepads", headers=headers)
        assert final_response.status_code == 200
        final_notepads = final_response.json()
        
        # Verify count increased
        assert len(final_notepads) == initial_count + 1, f"Expected {initial_count + 1}, got {len(final_notepads)}"
        
        # Verify the guest code is now in user's notepads
        codes = [n["code"] for n in final_notepads]
        assert guest_code.lower() in codes
        
        print(f"✓ GET /api/auth/notepads includes bulk-linked notepad (count: {len(final_notepads)})")
    
    def test_get_user_notepads_requires_auth(self, fresh_client):
        """Test GET /api/auth/notepads returns 401 without auth"""
        response = fresh_client.get(f"{BASE_URL}/api/auth/notepads")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/auth/notepads correctly requires auth")


# ==================== Single Link Still Works ====================

class TestSingleLinkStillWorks:
    """POST /api/auth/link-notepad - verify single link endpoint still works"""
    
    def test_single_link_notepad_still_works(self, fresh_client, api_client, existing_user_token):
        """Test single link notepad endpoint still functions correctly"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # Create guest notepad
        guest_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert guest_response.status_code == 200
        guest_code = guest_response.json()["code"]
        
        # Single link
        link_response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepad",
            json={"code": guest_code},
            headers=headers
        )
        
        assert link_response.status_code == 200, f"Expected 200, got {link_response.status_code}: {link_response.text}"
        data = link_response.json()
        
        # Verify response is the notepad
        assert data["code"] == guest_code.lower()
        assert data["account_type"] == "user"
        assert data.get("user_id") is not None
        
        print(f"✓ Single link notepad endpoint still works for code {guest_code}")


# ==================== Existing Auth Endpoints Still Work ====================

class TestExistingAuthEndpointsStillWork:
    """Verify existing auth endpoints are not broken"""
    
    def test_register_still_works(self, api_client):
        """Test user registration still works"""
        unique_email = f"TEST_verify_{uuid.uuid4().hex[:8]}@test.com"
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "testpass123",
            "name": "Verify Test"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        print("✓ POST /api/auth/register still works")
    
    def test_login_still_works(self, api_client):
        """Test login with existing user still works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "password123"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "test@test.com"
        print("✓ POST /api/auth/login still works")
    
    def test_get_me_still_works(self, api_client, existing_user_token):
        """Test GET /api/auth/me still works"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "id" in data
        assert "email" in data
        print("✓ GET /api/auth/me still works")


# ==================== Existing Notepad CRUD Still Works ====================

class TestExistingNotepadCRUDStillWorks:
    """Verify existing notepad CRUD operations are not broken"""
    
    def test_get_notepad_still_works(self, fresh_client):
        """Test GET /api/notepad/{code} still works"""
        # Create notepad
        create_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Get notepad
        response = fresh_client.get(f"{BASE_URL}/api/notepad/{code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.json()["code"] == code
        print("✓ GET /api/notepad/{code} still works")
    
    def test_append_notepad_still_works(self, fresh_client):
        """Test POST /api/notepad/{code}/append still works"""
        # Create notepad
        create_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Append text
        append_response = fresh_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": "Test append text"}
        )
        
        assert append_response.status_code == 200, f"Expected 200, got {append_response.status_code}"
        assert len(append_response.json()["entries"]) == 1
        print("✓ POST /api/notepad/{code}/append still works")
    
    def test_clear_notepad_still_works(self, fresh_client):
        """Test DELETE /api/notepad/{code} still works"""
        # Create notepad and add entry
        create_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        fresh_client.post(f"{BASE_URL}/api/notepad/{code}/append", json={"text": "To clear"})
        
        # Clear notepad
        response = fresh_client.delete(f"{BASE_URL}/api/notepad/{code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "cleared" in response.json().get("message", "").lower()
        print("✓ DELETE /api/notepad/{code} still works")


# ==================== Web Pages Still Work ====================

class TestWebPagesStillWork:
    """Verify web page rendering is not broken"""
    
    def test_landing_page_still_renders(self, api_client):
        """Test GET /api/ still renders"""
        response = api_client.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        print("✓ GET /api/ landing page still renders")
    
    def test_notepad_view_still_renders(self, fresh_client):
        """Test GET /api/notepad/{code}/view still renders"""
        # Create notepad
        create_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # View page
        response = fresh_client.get(f"{BASE_URL}/api/notepad/{code}/view")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        assert code in response.text
        print(f"✓ GET /api/notepad/{code}/view still renders")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
