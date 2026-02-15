"""
PasteBridge Backend API Tests
Tests for: Authentication (register, login, profile, password change), 
Notepad CRUD (create, view, append, clear), and user-notepad linking
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://clip-sync-1.preview.emergentagent.com').rstrip('/')

# Generate unique test email for each test run
TEST_EMAIL_SUFFIX = str(uuid.uuid4())[:8]

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_user_credentials():
    """Generate unique credentials for test user"""
    return {
        "email": f"TEST_user_{TEST_EMAIL_SUFFIX}@test.com",
        "password": "testpass123",
        "name": "Test User"
    }

@pytest.fixture(scope="module")
def registered_user(api_client, test_user_credentials):
    """Register a test user and return the auth response"""
    response = api_client.post(f"{BASE_URL}/api/auth/register", json=test_user_credentials)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 400 and "already registered" in response.text:
        # User exists, try to login
        login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        })
        if login_response.status_code == 200:
            return login_response.json()
    pytest.skip(f"Could not register or login test user: {response.text}")

@pytest.fixture(scope="module")
def auth_token(registered_user):
    """Get auth token from registered user"""
    return registered_user.get("token")

@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


# ==================== Health Check ====================

class TestHealth:
    """Health endpoint test"""
    
    def test_health_endpoint(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "PasteBridge API"
        print("✓ Health endpoint working")


# ==================== Registration Tests ====================

class TestRegistration:
    """POST /api/auth/register tests"""
    
    def test_register_new_user_success(self, api_client):
        """Test successful user registration"""
        unique_email = f"TEST_newuser_{uuid.uuid4().hex[:8]}@test.com"
        payload = {
            "email": unique_email,
            "password": "password123",
            "name": "New Test User"
        }
        response = api_client.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "user" in data
        assert "token" in data
        assert "message" in data
        
        # Verify user data
        assert data["user"]["email"] == unique_email.lower()
        assert data["user"]["name"] == "New Test User"
        assert data["user"]["account_type"] == "user"
        assert "id" in data["user"]
        
        # Verify token is present
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0
        
        print(f"✓ User registration successful: {unique_email}")
    
    def test_register_duplicate_email_rejected(self, api_client, test_user_credentials, registered_user):
        """Test duplicate email rejection returns 400"""
        payload = {
            "email": test_user_credentials["email"],
            "password": "anotherpassword",
            "name": "Duplicate User"
        }
        response = api_client.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "already registered" in data.get("detail", "").lower()
        print("✓ Duplicate email correctly rejected with 400")
    
    def test_register_short_password_rejected(self, api_client):
        """Test short password (<6 chars) rejection"""
        payload = {
            "email": f"TEST_short_{uuid.uuid4().hex[:8]}@test.com",
            "password": "12345",  # Only 5 chars
            "name": "Short Pass User"
        }
        response = api_client.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "6 characters" in data.get("detail", "").lower() or "password" in data.get("detail", "").lower()
        print("✓ Short password correctly rejected with 400")


# ==================== Login Tests ====================

class TestLogin:
    """POST /api/auth/login tests"""
    
    def test_login_success(self, api_client, test_user_credentials, registered_user):
        """Test successful login returns token"""
        payload = {
            "email": test_user_credentials["email"],
            "password": test_user_credentials["password"]
        }
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "user" in data
        assert "token" in data
        assert "message" in data
        
        # Verify user data
        assert data["user"]["email"] == test_user_credentials["email"].lower()
        assert data["message"] == "Login successful"
        
        # Verify token
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0
        
        print("✓ Login successful, token returned")
    
    def test_login_wrong_password_returns_401(self, api_client, test_user_credentials, registered_user):
        """Test wrong password returns 401"""
        payload = {
            "email": test_user_credentials["email"],
            "password": "wrongpassword123"
        }
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "invalid" in data.get("detail", "").lower()
        print("✓ Wrong password correctly rejected with 401")
    
    def test_login_nonexistent_email_returns_401(self, api_client):
        """Test non-existent email returns 401"""
        payload = {
            "email": "nonexistent_email_xyz123@doesnotexist.com",
            "password": "anypassword123"
        }
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=payload)
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "invalid" in data.get("detail", "").lower()
        print("✓ Non-existent email correctly rejected with 401")


# ==================== Auth Me Tests ====================

class TestAuthMe:
    """GET /api/auth/me tests"""
    
    def test_get_me_with_valid_token(self, api_client, auth_token, test_user_credentials):
        """Test getting user profile with valid token"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["email"] == test_user_credentials["email"].lower()
        assert "id" in data
        assert "account_type" in data
        assert "created_at" in data
        print("✓ GET /api/auth/me returns user profile with valid token")
    
    def test_get_me_without_token_returns_401(self, api_client):
        """Test getting profile without token returns 401"""
        # Create fresh session without auth header
        fresh_client = requests.Session()
        fresh_client.headers.update({"Content-Type": "application/json"})
        
        response = fresh_client.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/auth/me without token correctly returns 401")
    
    def test_get_me_with_invalid_token_returns_401(self, api_client):
        """Test getting profile with invalid token returns 401"""
        headers = {"Authorization": "Bearer invalid_token_xyz123"}
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/auth/me with invalid token correctly returns 401")


# ==================== Profile Update Tests ====================

class TestProfileUpdate:
    """PUT /api/auth/profile tests"""
    
    def test_update_profile_name(self, api_client, auth_token):
        """Test updating user name"""
        new_name = f"Updated Name {uuid.uuid4().hex[:4]}"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = api_client.put(
            f"{BASE_URL}/api/auth/profile",
            json={"name": new_name},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == new_name
        
        # Verify with GET /me
        verify_response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert verify_response.status_code == 200
        assert verify_response.json()["name"] == new_name
        
        print(f"✓ Profile name updated successfully to: {new_name}")


# ==================== Password Change Tests ====================

class TestPasswordChange:
    """POST /api/auth/change-password tests"""
    
    def test_change_password_success(self, api_client):
        """Test successful password change"""
        # Register a new user for this test
        unique_email = f"TEST_pwchange_{uuid.uuid4().hex[:8]}@test.com"
        old_password = "oldpassword123"
        new_password = "newpassword456"
        
        # Register
        reg_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": old_password,
            "name": "Password Change Test"
        })
        assert reg_response.status_code == 200
        token = reg_response.json()["token"]
        
        # Change password
        headers = {"Authorization": f"Bearer {token}"}
        response = api_client.post(
            f"{BASE_URL}/api/auth/change-password",
            json={
                "current_password": old_password,
                "new_password": new_password
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "success" in response.json().get("message", "").lower()
        
        # Verify old password no longer works
        login_old = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": old_password
        })
        assert login_old.status_code == 401
        
        # Verify new password works
        login_new = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": new_password
        })
        assert login_new.status_code == 200
        
        print("✓ Password changed successfully")
    
    def test_change_password_wrong_current_rejected(self, api_client, auth_token):
        """Test wrong current password rejection"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/auth/change-password",
            json={
                "current_password": "wrongcurrentpassword",
                "new_password": "newpassword123"
            },
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "incorrect" in response.json().get("detail", "").lower()
        print("✓ Wrong current password correctly rejected with 400")


# ==================== Notepad Creation Tests ====================

class TestNotepadCreation:
    """POST /api/notepad tests"""
    
    def test_create_notepad_guest(self, api_client):
        """Test creating notepad without authentication (guest)"""
        # Use fresh client without auth
        fresh_client = requests.Session()
        fresh_client.headers.update({"Content-Type": "application/json"})
        
        response = fresh_client.post(f"{BASE_URL}/api/notepad")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify notepad structure
        assert "id" in data
        assert "code" in data
        assert "entries" in data
        assert data["entries"] == []
        assert data["account_type"] == "guest"
        assert data.get("user_id") is None
        assert data.get("expires_at") is not None  # Guest notepads expire in 90 days
        
        print(f"✓ Guest notepad created with code: {data['code']}")
        return data["code"]
    
    def test_create_notepad_authenticated(self, api_client, auth_token):
        """Test creating notepad with authentication (linked to user)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify notepad structure
        assert "id" in data
        assert "code" in data
        assert data["account_type"] == "user"
        assert data.get("user_id") is not None
        assert data.get("expires_at") is not None  # User notepads expire in 365 days
        
        # Verify expiration is approximately 365 days from now
        expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
        now = datetime.utcnow()
        days_diff = (expires_at.replace(tzinfo=None) - now).days
        assert 360 <= days_diff <= 370, f"Expected ~365 days expiration, got {days_diff}"
        
        print(f"✓ Authenticated notepad created with code: {data['code']}, account_type: user")
        return data["code"]


# ==================== User Notepads Tests ====================

class TestUserNotepads:
    """GET /api/auth/notepads tests"""
    
    def test_get_user_notepads(self, api_client, auth_token):
        """Test getting user's linked notepads"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # First create a notepad with auth
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        created_code = create_response.json()["code"]
        
        # Get user's notepads
        response = api_client.get(f"{BASE_URL}/api/auth/notepads", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify created notepad is in list
        codes = [n["code"] for n in data]
        assert created_code in codes
        
        print(f"✓ User notepads returned: {len(data)} notepad(s)")


# ==================== Link Notepad Tests ====================

class TestLinkNotepad:
    """POST /api/auth/link-notepad tests"""
    
    def test_link_guest_notepad_to_user(self, api_client, auth_token):
        """Test linking a guest notepad to user account"""
        # Create guest notepad (no auth)
        fresh_client = requests.Session()
        fresh_client.headers.update({"Content-Type": "application/json"})
        
        guest_response = fresh_client.post(f"{BASE_URL}/api/notepad")
        assert guest_response.status_code == 200
        guest_code = guest_response.json()["code"]
        guest_data = guest_response.json()
        
        assert guest_data["account_type"] == "guest"
        assert guest_data.get("user_id") is None
        
        # Link to user
        headers = {"Authorization": f"Bearer {auth_token}"}
        link_response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepad",
            json={"code": guest_code},
            headers=headers
        )
        
        assert link_response.status_code == 200, f"Expected 200, got {link_response.status_code}: {link_response.text}"
        data = link_response.json()
        
        assert data["code"] == guest_code
        assert data["account_type"] == "user"
        assert data.get("user_id") is not None
        
        print(f"✓ Guest notepad {guest_code} linked to user account")
    
    def test_link_already_linked_notepad_rejected(self, api_client, auth_token):
        """Test linking already-linked notepad is rejected"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create user notepad (already linked)
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        linked_code = create_response.json()["code"]
        
        # Try to link again
        link_response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepad",
            json={"code": linked_code},
            headers=headers
        )
        
        assert link_response.status_code == 400, f"Expected 400, got {link_response.status_code}"
        assert "already" in link_response.json().get("detail", "").lower()
        
        print("✓ Already-linked notepad correctly rejected with 400")
    
    def test_link_nonexistent_notepad_returns_404(self, api_client, auth_token):
        """Test linking non-existent notepad returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        link_response = api_client.post(
            f"{BASE_URL}/api/auth/link-notepad",
            json={"code": "nonexistent_code_xyz123"},
            headers=headers
        )
        
        assert link_response.status_code == 404, f"Expected 404, got {link_response.status_code}"
        print("✓ Non-existent notepad correctly returns 404")


# ==================== Notepad CRUD Tests ====================

class TestNotepadCRUD:
    """GET, POST append, DELETE notepad tests"""
    
    @pytest.fixture(scope="class")
    def test_notepad(self, api_client):
        """Create a notepad for testing"""
        response = api_client.post(f"{BASE_URL}/api/notepad")
        assert response.status_code == 200
        return response.json()["code"]
    
    def test_get_notepad(self, api_client, test_notepad):
        """Test GET /api/notepad/{code}"""
        response = api_client.get(f"{BASE_URL}/api/notepad/{test_notepad}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["code"] == test_notepad
        assert "entries" in data
        assert "expires_at" in data
        
        print(f"✓ GET notepad {test_notepad} successful")
    
    def test_get_nonexistent_notepad_returns_404(self, api_client):
        """Test GET non-existent notepad returns 404"""
        response = api_client.get(f"{BASE_URL}/api/notepad/nonexistent_xyz123")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent notepad correctly returns 404")
    
    def test_append_to_notepad(self, api_client, test_notepad):
        """Test POST /api/notepad/{code}/append"""
        test_text = f"Test entry at {datetime.utcnow().isoformat()}"
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad}/append",
            json={"text": test_text}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert len(data["entries"]) >= 1
        # Check latest entry
        found = any(entry["text"] == test_text for entry in data["entries"])
        assert found, "Appended text not found in entries"
        
        print(f"✓ Text appended to notepad {test_notepad}")
    
    def test_clear_notepad(self, api_client, test_notepad):
        """Test DELETE /api/notepad/{code} clears entries"""
        # First append something
        api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad}/append",
            json={"text": "Entry to be cleared"}
        )
        
        # Clear notepad
        response = api_client.delete(f"{BASE_URL}/api/notepad/{test_notepad}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "cleared" in response.json().get("message", "").lower()
        
        # Verify entries are empty
        verify_response = api_client.get(f"{BASE_URL}/api/notepad/{test_notepad}")
        assert verify_response.status_code == 200
        assert verify_response.json()["entries"] == []
        
        print(f"✓ Notepad {test_notepad} cleared successfully")


# ==================== Web Pages Tests ====================

class TestWebPages:
    """Web page rendering tests"""
    
    def test_landing_page_renders(self, api_client):
        """Test GET /api/ renders landing page"""
        response = api_client.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/html" in response.headers.get("content-type", "")
        
        content = response.text
        assert "PasteBridge" in content
        assert "Enter your notepad code" in content or "notepad code" in content.lower()
        
        print("✓ Landing page renders correctly")
    
    def test_notepad_view_page_renders(self, api_client):
        """Test GET /api/notepad/{code}/view renders with entries"""
        # First create a notepad with some entries
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Add an entry
        api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": "Test entry for view page"}
        )
        
        # Test the view page
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/view")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/html" in response.headers.get("content-type", "")
        
        content = response.text
        assert "PasteBridge" in content
        assert code in content
        assert "Test entry for view page" in content
        
        print(f"✓ Notepad view page for {code} renders correctly with entries")
    
    def test_notepad_view_not_found(self, api_client):
        """Test GET /api/notepad/{code}/view for non-existent notepad"""
        response = api_client.get(f"{BASE_URL}/api/notepad/nonexistent_xyz123/view")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        content = response.text
        assert "not found" in content.lower()
        
        print("✓ Non-existent notepad view page returns 404")


# ==================== Existing User Tests ====================

class TestExistingUser:
    """Tests using the existing test@test.com user"""
    
    def test_login_existing_user(self, api_client):
        """Test login with existing test@test.com user"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "password123"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["user"]["email"] == "test@test.com"
        assert "token" in data
        
        print("✓ Existing user test@test.com login successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
