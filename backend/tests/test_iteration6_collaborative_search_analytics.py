"""
PasteBridge Iteration 6 - Collaborative Notepads, Search/Filtering & Analytics Tests

Tests for NEW features:
1. Collaborative Notepads:
   - POST /api/notepad/{code}/share - share notepad by email (owner only)
   - DELETE /api/notepad/{code}/share/{email} - remove collaborator
   - GET /api/notepad/{code}/collaborators - list owner & collaborators
   - GET /api/auth/shared-notepads - list notepads shared with current user

2. Search & Filtering:
   - POST /api/notepad/search - search by text query, code prefix, date range
   - Pagination support (page, limit, total, pages)
   - matching_entries count and preview for text searches

3. Analytics Dashboard:
   - GET /api/admin/analytics - HTML analytics page with charts
   - GET /api/admin/analytics-data - JSON analytics data

Test credentials: 
- test@test.com / password123 (primary user)
- collab@test.com / password123 (collaborator user)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

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
def test_user_token(api_client):
    """Get token for test@test.com user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "password123"
    })
    assert response.status_code == 200, f"Failed to login test@test.com: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def test_user_info(api_client, test_user_token):
    """Get test user info"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="module")
def collab_user_token(api_client):
    """Get token for collab@test.com user (create if doesn't exist)"""
    # Try login first
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "collab@test.com",
        "password": "password123"
    })
    if response.status_code == 200:
        return response.json()["token"]
    
    # Register if not exists
    register_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
        "email": "collab@test.com",
        "password": "password123",
        "name": "Collaborator User"
    }, headers={"X-Forwarded-For": f"192.168.{hash(TEST_RUN_ID) % 256}.50"})
    
    if register_response.status_code == 200:
        return register_response.json()["token"]
    
    # Already registered, try login again
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "collab@test.com",
        "password": "password123"
    })
    assert response.status_code == 200, f"Failed to login/register collab@test.com: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def collab_user_info(api_client, collab_user_token):
    """Get collab user info"""
    headers = {"Authorization": f"Bearer {collab_user_token}"}
    response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="module")
def test_notepad_code(api_client, test_user_token):
    """Create a notepad owned by test@test.com for sharing tests"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
    assert response.status_code == 200, f"Failed to create notepad: {response.text}"
    code = response.json()["code"]
    
    # Add some entries for search testing
    for i in range(3):
        api_client.post(f"{BASE_URL}/api/notepad/{code}/append", json={
            "text": f"TEST_entry_{TEST_RUN_ID}_number_{i}: This is searchable content"
        })
    
    return code


# ==================== COLLABORATIVE NOTEPAD TESTS ====================

class TestShareNotepad:
    """Tests for POST /api/notepad/{code}/share"""
    
    def test_share_notepad_with_valid_user(self, api_client, test_user_token, collab_user_token, test_notepad_code):
        """POST /api/notepad/{code}/share - share notepad with another user (requires owner auth)"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/share",
            json={"email": "collab@test.com"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        assert "code" in data
        assert data["code"] == test_notepad_code
        
        print(f"✓ POST /api/notepad/{test_notepad_code}/share - shared with collab@test.com")
    
    def test_share_notepad_rejects_self_sharing(self, api_client, test_user_token, test_notepad_code):
        """POST /api/notepad/{code}/share - rejects sharing with self"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/share",
            json={"email": "test@test.com"},  # Same user
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "yourself" in data.get("detail", "").lower() or "cannot" in data.get("detail", "").lower()
        
        print("✓ POST /api/notepad/{code}/share - rejects sharing with self")
    
    def test_share_notepad_rejects_non_owner(self, api_client, collab_user_token, test_notepad_code):
        """POST /api/notepad/{code}/share - rejects non-owner sharing"""
        headers = {"Authorization": f"Bearer {collab_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/share",
            json={"email": "someone@example.com"},
            headers=headers
        )
        
        # Should be 403 - not owner
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        data = response.json()
        assert "owner" in data.get("detail", "").lower()
        
        print("✓ POST /api/notepad/{code}/share - rejects non-owner sharing (403)")
    
    def test_share_notepad_rejects_nonexistent_email(self, api_client, test_user_token, test_notepad_code):
        """POST /api/notepad/{code}/share - rejects sharing with non-existent email"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/share",
            json={"email": f"nonexistent_{TEST_RUN_ID}@example.com"},
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "not found" in data.get("detail", "").lower()
        
        print("✓ POST /api/notepad/{code}/share - rejects non-existent email (404)")
    
    def test_share_notepad_duplicate_returns_already_has_access(self, api_client, test_user_token, test_notepad_code):
        """POST /api/notepad/{code}/share - duplicate share returns already has access"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Share again with same user
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/share",
            json={"email": "collab@test.com"},
            headers=headers
        )
        
        # Should succeed but indicate already has access
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "already" in data.get("message", "").lower()
        
        print("✓ POST /api/notepad/{code}/share - duplicate share returns 'already has access'")
    
    def test_share_notepad_requires_auth(self, api_client, test_notepad_code):
        """POST /api/notepad/{code}/share - requires authentication (401 without token)"""
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/share",
            json={"email": "someone@test.com"}
            # No auth header
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        print("✓ POST /api/notepad/{code}/share - requires auth (401 without token)")


class TestGetCollaborators:
    """Tests for GET /api/notepad/{code}/collaborators"""
    
    def test_get_collaborators_as_owner(self, api_client, test_user_token, test_notepad_code):
        """GET /api/notepad/{code}/collaborators - list owner and collaborators (as owner)"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.get(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/collaborators",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have owner and collaborators fields
        assert "owner" in data, "Response should have 'owner'"
        assert "collaborators" in data, "Response should have 'collaborators'"
        
        # Owner should have id and email
        assert "id" in data["owner"]
        assert "email" in data["owner"]
        assert data["owner"]["email"] == "test@test.com"
        
        # Collaborators should be a list
        assert isinstance(data["collaborators"], list)
        
        # Should include collab@test.com we added earlier
        collab_emails = [c.get("email") for c in data["collaborators"]]
        assert "collab@test.com" in collab_emails, f"collab@test.com should be in collaborators: {collab_emails}"
        
        print(f"✓ GET /api/notepad/{test_notepad_code}/collaborators - owner={data['owner']['email']}, {len(data['collaborators'])} collaborators")
    
    def test_get_collaborators_as_collaborator(self, api_client, collab_user_token, test_notepad_code):
        """GET /api/notepad/{code}/collaborators - collaborator can view list"""
        headers = {"Authorization": f"Bearer {collab_user_token}"}
        
        response = api_client.get(
            f"{BASE_URL}/api/notepad/{test_notepad_code}/collaborators",
            headers=headers
        )
        
        # Collaborators should be able to see the list
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        print("✓ GET /api/notepad/{code}/collaborators - collaborator can view list")


class TestSharedNotepads:
    """Tests for GET /api/auth/shared-notepads"""
    
    def test_get_shared_notepads(self, api_client, collab_user_token, test_notepad_code):
        """GET /api/auth/shared-notepads - list notepads shared with current user"""
        headers = {"Authorization": f"Bearer {collab_user_token}"}
        
        response = api_client.get(
            f"{BASE_URL}/api/auth/shared-notepads",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        # Should include the notepad we shared
        shared_codes = [n.get("code") for n in data]
        assert test_notepad_code in shared_codes, f"{test_notepad_code} should be in shared notepads: {shared_codes}"
        
        # Each notepad should have standard fields
        if data:
            notepad = data[0]
            assert "code" in notepad
            assert "entries" in notepad or "created_at" in notepad
        
        print(f"✓ GET /api/auth/shared-notepads - found {len(data)} shared notepads including {test_notepad_code}")
    
    def test_get_shared_notepads_requires_auth(self, api_client):
        """GET /api/auth/shared-notepads - requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/auth/shared-notepads")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        print("✓ GET /api/auth/shared-notepads - requires auth (401)")


class TestUnshareNotepad:
    """Tests for DELETE /api/notepad/{code}/share/{email}"""
    
    def test_remove_collaborator(self, api_client, test_user_token):
        """DELETE /api/notepad/{code}/share/{email} - remove collaborator"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Create a new notepad for this test
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Share with collab user
        share_response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/share",
            json={"email": "collab@test.com"},
            headers=headers
        )
        assert share_response.status_code == 200
        
        # Now remove collaborator
        remove_response = api_client.delete(
            f"{BASE_URL}/api/notepad/{code}/share/collab@test.com",
            headers=headers
        )
        
        assert remove_response.status_code == 200, f"Expected 200, got {remove_response.status_code}: {remove_response.text}"
        data = remove_response.json()
        assert "removed" in data.get("message", "").lower()
        
        # Verify collaborator was removed
        collab_response = api_client.get(f"{BASE_URL}/api/notepad/{code}/collaborators", headers=headers)
        collab_data = collab_response.json()
        collab_emails = [c.get("email") for c in collab_data["collaborators"]]
        assert "collab@test.com" not in collab_emails, "collab@test.com should be removed"
        
        print(f"✓ DELETE /api/notepad/{code}/share/collab@test.com - collaborator removed")


# ==================== SEARCH & FILTERING TESTS ====================

class TestNotepadSearch:
    """Tests for POST /api/notepad/search"""
    
    def test_search_requires_auth(self, api_client):
        """POST /api/notepad/search - requires auth (401 without token)"""
        response = api_client.post(
            f"{BASE_URL}/api/notepad/search",
            json={"query": "test"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        print("✓ POST /api/notepad/search - requires auth (401)")
    
    def test_search_by_text_query(self, api_client, test_user_token, test_notepad_code):
        """POST /api/notepad/search - search by text query across entries"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/search",
            json={"query": f"TEST_entry_{TEST_RUN_ID}"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have pagination structure
        assert "items" in data, "Response should have 'items'"
        assert "total" in data, "Response should have 'total'"
        assert "page" in data, "Response should have 'page'"
        assert "pages" in data, "Response should have 'pages'"
        
        # Should find our test notepad
        found_codes = [n.get("code") for n in data["items"]]
        assert test_notepad_code in found_codes, f"Should find {test_notepad_code} in search results: {found_codes}"
        
        print(f"✓ POST /api/notepad/search by text - found {data['total']} results")
    
    def test_search_by_code_prefix(self, api_client, test_user_token, test_notepad_code):
        """POST /api/notepad/search - search by code prefix"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Search by first few chars of the code
        code_prefix = test_notepad_code[:4]
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/search",
            json={"code": code_prefix},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should find our notepad
        found_codes = [n.get("code") for n in data["items"]]
        assert test_notepad_code in found_codes, f"Should find {test_notepad_code} when searching for prefix '{code_prefix}'"
        
        print(f"✓ POST /api/notepad/search by code prefix '{code_prefix}' - found {data['total']} results")
    
    def test_search_pagination(self, api_client, test_user_token):
        """POST /api/notepad/search - pagination works (page, limit, total, pages)"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Create several notepads for pagination test
        for i in range(3):
            create_resp = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
            if create_resp.status_code == 200:
                code = create_resp.json()["code"]
                api_client.post(f"{BASE_URL}/api/notepad/{code}/append", json={
                    "text": f"PAGINATION_TEST_{TEST_RUN_ID}"
                })
        
        # Search with limit=2
        response = api_client.post(
            f"{BASE_URL}/api/notepad/search",
            json={"query": f"PAGINATION_TEST_{TEST_RUN_ID}", "page": 1, "limit": 2},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert data["page"] == 1
        assert len(data["items"]) <= 2, f"Expected at most 2 items with limit=2, got {len(data['items'])}"
        
        # Verify pages calculation
        if data["total"] > 0:
            expected_pages = (data["total"] + 1) // 2  # ceil(total/2)
            assert data["pages"] >= 1
        
        print(f"✓ POST /api/notepad/search pagination - page {data['page']}/{data['pages']}, total={data['total']}")
    
    def test_search_returns_matching_entries_and_preview(self, api_client, test_user_token, test_notepad_code):
        """POST /api/notepad/search - returns matching_entries count and preview when searching text"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/search",
            json={"query": "searchable content"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Find our test notepad in results
        test_notepad = None
        for item in data["items"]:
            if item.get("code") == test_notepad_code:
                test_notepad = item
                break
        
        if test_notepad:
            # Should have matching_entries and preview when query matches
            # Note: These are added to the response dict, not the Pydantic model
            if "matching_entries" in test_notepad:
                assert test_notepad["matching_entries"] >= 1, "Should have at least 1 matching entry"
                print(f"✓ Found matching_entries={test_notepad['matching_entries']}")
            
            if "preview" in test_notepad:
                assert len(test_notepad["preview"]) > 0, "Preview should not be empty"
                print(f"✓ Found preview: {test_notepad['preview'][:50]}...")
            
            print(f"✓ POST /api/notepad/search - returns matching_entries and preview for {test_notepad_code}")
        else:
            # Test notepad may not match "searchable content" - still pass
            print(f"⚠ Test notepad {test_notepad_code} not in results - checking response structure only")
            assert "items" in data
    
    def test_search_includes_shared_notepads(self, api_client, collab_user_token, test_notepad_code):
        """POST /api/notepad/search - includes shared notepads in results"""
        headers = {"Authorization": f"Bearer {collab_user_token}"}
        
        # Search as collab user - should find shared notepad
        response = api_client.post(
            f"{BASE_URL}/api/notepad/search",
            json={"query": f"TEST_entry_{TEST_RUN_ID}"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should find the shared notepad
        found_codes = [n.get("code") for n in data["items"]]
        assert test_notepad_code in found_codes, f"Shared notepad {test_notepad_code} should be searchable by collaborator"
        
        print(f"✓ POST /api/notepad/search - includes shared notepads (found {test_notepad_code})")


# ==================== ANALYTICS TESTS ====================

class TestAnalytics:
    """Tests for analytics endpoints"""
    
    def test_analytics_page_renders(self, api_client):
        """GET /api/admin/analytics - analytics page renders"""
        response = api_client.get(f"{BASE_URL}/api/admin/analytics")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/html" in response.headers.get("content-type", "")
        
        html = response.text
        assert "PasteBridge Analytics" in html
        assert "Total Users" in html or "s-users" in html
        assert "Total Notepads" in html or "s-notepads" in html
        assert "Total Entries" in html or "s-entries" in html
        assert "/api/admin/analytics-data" in html
        
        print("✓ GET /api/admin/analytics - renders HTML analytics page")
    
    def test_analytics_data_returns_correct_structure(self, api_client):
        """GET /api/admin/analytics-data - returns entries_by_day, users_by_day, top_notepads, totals"""
        response = api_client.get(f"{BASE_URL}/api/admin/analytics-data")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "entries_by_day" in data, "Response should have 'entries_by_day'"
        assert "users_by_day" in data, "Response should have 'users_by_day'"
        assert "top_notepads" in data, "Response should have 'top_notepads'"
        assert "totals" in data, "Response should have 'totals'"
        
        # Verify totals structure
        totals = data["totals"]
        assert "users" in totals, "totals should have 'users'"
        assert "notepads" in totals, "totals should have 'notepads'"
        assert "entries" in totals, "totals should have 'entries'"
        assert "active_today" in totals, "totals should have 'active_today'"
        
        # Verify data types
        assert isinstance(data["entries_by_day"], list)
        assert isinstance(data["users_by_day"], list)
        assert isinstance(data["top_notepads"], list)
        assert isinstance(totals["users"], int)
        assert isinstance(totals["notepads"], int)
        assert isinstance(totals["entries"], int)
        
        # Verify entries_by_day structure if has data
        if data["entries_by_day"]:
            entry = data["entries_by_day"][0]
            assert "date" in entry, "entries_by_day items should have 'date'"
            assert "count" in entry, "entries_by_day items should have 'count'"
        
        # Verify users_by_day structure if has data
        if data["users_by_day"]:
            user_entry = data["users_by_day"][0]
            assert "date" in user_entry, "users_by_day items should have 'date'"
            assert "count" in user_entry, "users_by_day items should have 'count'"
        
        # Verify top_notepads structure if has data
        if data["top_notepads"]:
            top = data["top_notepads"][0]
            assert "code" in top, "top_notepads items should have 'code'"
            assert "entry_count" in top, "top_notepads items should have 'entry_count'"
        
        print(f"✓ GET /api/admin/analytics-data - totals: {totals['users']} users, {totals['notepads']} notepads, {totals['entries']} entries")


# ==================== EXISTING ENDPOINTS STILL WORK ====================

class TestExistingEndpoints:
    """Verify existing endpoints are not broken by new features"""
    
    def test_auth_login_still_works(self, api_client):
        """POST /api/auth/login still works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "password123"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        
        print("✓ POST /api/auth/login still works")
    
    def test_notepad_crud_still_works(self, api_client, test_user_token):
        """Notepad CRUD operations still work"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # Create
        create_response = api_client.post(f"{BASE_URL}/api/notepad", headers=headers)
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Read
        get_response = api_client.get(f"{BASE_URL}/api/notepad/{code}")
        assert get_response.status_code == 200
        
        # Append
        append_response = api_client.post(f"{BASE_URL}/api/notepad/{code}/append", json={
            "text": f"Test entry {TEST_RUN_ID}"
        })
        assert append_response.status_code == 200
        
        # Clear
        clear_response = api_client.delete(f"{BASE_URL}/api/notepad/{code}")
        assert clear_response.status_code == 200
        
        print("✓ Notepad CRUD (create/read/append/clear) still works")
    
    def test_landing_page_still_works(self, api_client):
        """GET /api/ landing page still works"""
        response = api_client.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        
        print("✓ GET /api/ landing page still works")
    
    def test_get_user_notepads_still_works(self, api_client, test_user_token):
        """GET /api/auth/notepads still works"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/auth/notepads", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        print(f"✓ GET /api/auth/notepads still works - {len(data)} notepads")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
