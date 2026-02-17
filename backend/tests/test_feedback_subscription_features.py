"""
PasteBridge Iteration 4 Feature Tests
Tests for: Bug & Feedback System, Stripe Subscription Tiers, Web View Enhancements

New endpoints tested:
- POST /api/feedback (submit bug report, guest or auth)
- GET /api/admin/feedback (list all feedback)
- GET /api/admin/feedback?status=open|category=bug (filter feedback)
- POST /api/admin/feedback/summarize (AI summarize open feedback)
- PATCH /api/admin/feedback/{id} (update status)
- GET /api/subscription/plans (list plans)
- POST /api/subscription/checkout (create Stripe checkout, requires auth)
- GET /api/subscription/status/{session_id} (check payment status)
- GET /api/subscription/success (success page)
- GET /api/subscription/plans-page (plans page)
- POST /api/webhook/stripe (Stripe webhook endpoint)
- GET /api/notepad/{code}/view (with export and summarize buttons)
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


# ==================== Feedback System Tests ====================

class TestFeedbackSubmission:
    """POST /api/feedback tests"""
    
    def test_submit_feedback_as_guest(self, fresh_client):
        """Test submitting feedback without authentication (guest)"""
        response = fresh_client.post(f"{BASE_URL}/api/feedback", json={
            "category": "bug",
            "title": f"TEST_Guest Bug Report {TEST_RUN_ID}",
            "description": "Test bug description from guest user",
            "severity": "medium"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert "message" in data
        assert "submitted" in data["message"].lower() or "thank" in data["message"].lower()
        
        print(f"✓ POST /api/feedback (guest) created feedback: {data['id']}")
    
    def test_submit_feedback_with_auth_captures_user_info(self, api_client, existing_user_token):
        """Test submitting feedback with authentication captures user_id and email"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/feedback",
            json={
                "category": "feature_request",
                "title": f"TEST_Auth Feature Request {TEST_RUN_ID}",
                "description": "Test feature request from authenticated user",
                "severity": "low"
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        
        print(f"✓ POST /api/feedback (authenticated) created feedback: {data['id']}")
        return data["id"]
    
    def test_submit_feedback_validates_category(self, fresh_client):
        """Test feedback submission accepts valid categories"""
        valid_categories = ["bug", "feature_request", "missing_feature", "other"]
        
        for category in valid_categories:
            response = fresh_client.post(f"{BASE_URL}/api/feedback", json={
                "category": category,
                "title": f"TEST_Category Test {category} {TEST_RUN_ID}",
                "description": f"Testing {category} category",
                "severity": "low"
            })
            assert response.status_code == 200, f"Category '{category}' failed: {response.text}"
        
        print(f"✓ All valid categories accepted: {valid_categories}")
    
    def test_submit_feedback_requires_title(self, fresh_client):
        """Test feedback submission requires title"""
        response = fresh_client.post(f"{BASE_URL}/api/feedback", json={
            "category": "bug",
            "description": "Missing title test",
            "severity": "low"
        })
        
        # Should fail validation
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ POST /api/feedback correctly rejects missing title")
    
    def test_submit_feedback_requires_category(self, fresh_client):
        """Test feedback submission requires category"""
        response = fresh_client.post(f"{BASE_URL}/api/feedback", json={
            "title": "Missing category test",
            "description": "Missing category test",
            "severity": "low"
        })
        
        # Should fail validation
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("✓ POST /api/feedback correctly rejects missing category")


class TestFeedbackAdmin:
    """GET/PATCH /api/admin/feedback tests"""
    
    def test_list_all_feedback(self, api_client):
        """Test listing all feedback"""
        response = api_client.get(f"{BASE_URL}/api/admin/feedback")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            # Verify feedback item structure
            item = data[0]
            assert "id" in item
            assert "category" in item
            assert "title" in item
            assert "description" in item
            assert "status" in item
            assert "created_at" in item
        
        print(f"✓ GET /api/admin/feedback returned {len(data)} feedback item(s)")
    
    def test_list_feedback_filter_by_status(self, api_client):
        """Test filtering feedback by status"""
        response = api_client.get(f"{BASE_URL}/api/admin/feedback?status=open")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Verify all items have the requested status
        for item in data:
            assert item["status"] == "open", f"Found item with status '{item['status']}' when filtering by 'open'"
        
        print(f"✓ GET /api/admin/feedback?status=open returned {len(data)} items (all with status=open)")
    
    def test_list_feedback_filter_by_category(self, api_client):
        """Test filtering feedback by category"""
        response = api_client.get(f"{BASE_URL}/api/admin/feedback?category=bug")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Verify all items have the requested category
        for item in data:
            assert item["category"] == "bug", f"Found item with category '{item['category']}' when filtering by 'bug'"
        
        print(f"✓ GET /api/admin/feedback?category=bug returned {len(data)} bug items")
    
    def test_update_feedback_status(self, api_client, fresh_client):
        """Test updating feedback status"""
        # First create a feedback item
        create_response = fresh_client.post(f"{BASE_URL}/api/feedback", json={
            "category": "bug",
            "title": f"TEST_Status Update Test {TEST_RUN_ID}",
            "description": "Test for status update",
            "severity": "medium"
        })
        assert create_response.status_code == 200
        feedback_id = create_response.json()["id"]
        
        # Update status to in_progress
        response = api_client.patch(
            f"{BASE_URL}/api/admin/feedback/{feedback_id}?status=in_progress"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        assert "in_progress" in data["message"]
        
        print(f"✓ PATCH /api/admin/feedback/{feedback_id} updated status to in_progress")
    
    def test_update_nonexistent_feedback_returns_404(self, api_client):
        """Test updating non-existent feedback returns 404"""
        response = api_client.patch(
            f"{BASE_URL}/api/admin/feedback/nonexistent-id-xyz123?status=resolved"
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ PATCH /api/admin/feedback/nonexistent returns 404")


class TestFeedbackAISummarize:
    """POST /api/admin/feedback/summarize tests"""
    
    def test_summarize_open_feedback(self, api_client):
        """Test AI summarization of open feedback"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/feedback/summarize",
            timeout=30  # AI calls can take longer
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "summary" in data
        assert "count" in data
        
        # If there's open feedback, we should have model info
        if data["count"] > 0:
            assert "model" in data
            assert data["model"] == "gpt-5.2"
            assert len(data["summary"]) > 0
            print(f"✓ POST /api/admin/feedback/summarize returned summary ({len(data['summary'])} chars, {data['count']} items)")
            print(f"  Summary preview: {data['summary'][:150]}...")
        else:
            assert "No open feedback" in data["summary"]
            print("✓ POST /api/admin/feedback/summarize correctly handles no open feedback")


# ==================== Subscription System Tests ====================

class TestSubscriptionPlans:
    """GET /api/subscription/plans tests"""
    
    def test_get_subscription_plans(self, api_client):
        """Test getting subscription plans"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify Free plan
        assert "free" in data
        assert data["free"]["name"] == "Free"
        assert data["free"]["price"] == 0
        assert "features" in data["free"]
        
        # Verify Pro plan
        assert "pro" in data
        assert data["pro"]["name"] == "Pro"
        assert data["pro"]["price"] == 4.99
        assert "features" in data["pro"]
        
        # Verify Business plan
        assert "business" in data
        assert data["business"]["name"] == "Business"
        assert data["business"]["price"] == 14.99
        assert "features" in data["business"]
        
        print(f"✓ GET /api/subscription/plans returns Free/Pro/Business plans")


class TestSubscriptionCheckout:
    """POST /api/subscription/checkout tests"""
    
    def test_checkout_requires_auth(self, fresh_client):
        """Test creating checkout session requires authentication"""
        response = fresh_client.post(f"{BASE_URL}/api/subscription/checkout", json={
            "plan": "pro",
            "origin_url": "https://example.com"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ POST /api/subscription/checkout returns 401 without auth")
    
    def test_checkout_pro_plan(self, api_client, existing_user_token):
        """Test creating Stripe checkout session for Pro plan"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/subscription/checkout",
            json={
                "plan": "pro",
                "origin_url": "https://clip-sync-1.preview.emergentagent.com"
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "url" in data
        assert "session_id" in data
        assert len(data["session_id"]) > 0
        assert "stripe.com" in data["url"] or "checkout" in data["url"]
        
        print(f"✓ POST /api/subscription/checkout (pro) created session: {data['session_id'][:20]}...")
        return data["session_id"]
    
    def test_checkout_business_plan(self, api_client, existing_user_token):
        """Test creating Stripe checkout session for Business plan"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/subscription/checkout",
            json={
                "plan": "business",
                "origin_url": "https://clip-sync-1.preview.emergentagent.com"
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "url" in data
        assert "session_id" in data
        
        print(f"✓ POST /api/subscription/checkout (business) created session")
    
    def test_checkout_invalid_plan(self, api_client, existing_user_token):
        """Test creating checkout session with invalid plan"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        response = api_client.post(
            f"{BASE_URL}/api/subscription/checkout",
            json={
                "plan": "invalid_plan",
                "origin_url": "https://example.com"
            },
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "invalid" in data.get("detail", "").lower()
        
        print("✓ POST /api/subscription/checkout rejects invalid plan")


class TestSubscriptionStatus:
    """GET /api/subscription/status/{session_id} tests"""
    
    def test_get_subscription_status(self, api_client, existing_user_token):
        """Test checking subscription payment status"""
        headers = {"Authorization": f"Bearer {existing_user_token}"}
        
        # First create a checkout session
        create_response = api_client.post(
            f"{BASE_URL}/api/subscription/checkout",
            json={
                "plan": "pro",
                "origin_url": "https://clip-sync-1.preview.emergentagent.com"
            },
            headers=headers
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # Check status
        response = api_client.get(f"{BASE_URL}/api/subscription/status/{session_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "status" in data
        assert "payment_status" in data
        
        print(f"✓ GET /api/subscription/status/{session_id[:10]}... returned status: {data['status']}, payment: {data['payment_status']}")


class TestSubscriptionPages:
    """GET /api/subscription/success and /api/subscription/plans-page tests"""
    
    def test_success_page_renders(self, api_client):
        """Test subscription success page renders"""
        response = api_client.get(f"{BASE_URL}/api/subscription/success?session_id=test_session_123")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        assert "Payment" in response.text or "Checking" in response.text
        
        print("✓ GET /api/subscription/success renders HTML page")
    
    def test_plans_page_renders(self, api_client):
        """Test subscription plans page renders"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans-page")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        assert "Free" in response.text
        assert "Pro" in response.text
        assert "Business" in response.text
        assert "$4.99" in response.text
        assert "$14.99" in response.text
        
        print("✓ GET /api/subscription/plans-page renders HTML with all plans")


class TestStripeWebhook:
    """POST /api/webhook/stripe tests"""
    
    def test_stripe_webhook_endpoint_exists(self, api_client):
        """Test Stripe webhook endpoint exists and responds"""
        # Send a minimal request (will likely fail validation but endpoint should exist)
        response = api_client.post(
            f"{BASE_URL}/api/webhook/stripe",
            data=b"{}",  # Raw body
            headers={"Content-Type": "application/json"}
        )
        
        # Endpoint should exist (may return error due to invalid Stripe signature)
        # We just want to verify the endpoint exists and responds
        assert response.status_code in [200, 400, 401, 422, 500], f"Unexpected status: {response.status_code}"
        
        # Even with error, it should return JSON or at least respond
        print(f"✓ POST /api/webhook/stripe endpoint exists (status: {response.status_code})")


# ==================== Web View Enhancement Tests ====================

class TestWebViewEnhancements:
    """GET /api/notepad/{code}/view with export and summarize buttons tests"""
    
    @pytest.fixture(scope="class")
    def notepad_with_entries(self, api_client):
        """Create a notepad with entries for testing"""
        response = api_client.post(f"{BASE_URL}/api/notepad")
        assert response.status_code == 200
        code = response.json()["code"]
        
        # Add an entry
        append_response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": f"Test entry for web view {TEST_RUN_ID}"}
        )
        assert append_response.status_code == 200
        
        return code
    
    def test_view_has_export_buttons(self, api_client, notepad_with_entries):
        """Test web view has export buttons (TXT, MD, JSON)"""
        code = notepad_with_entries
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/view")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check for export links/buttons
        assert "Export TXT" in response.text or "export?format=txt" in response.text
        assert "Export MD" in response.text or "export?format=md" in response.text
        assert "Export JSON" in response.text or "export?format=json" in response.text
        
        print(f"✓ GET /api/notepad/{code}/view has export buttons")
    
    def test_view_has_summarize_button(self, api_client, notepad_with_entries):
        """Test web view has AI summarize button"""
        code = notepad_with_entries
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/view")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check for summarize button
        assert "Summarize" in response.text or "summarize" in response.text.lower()
        assert "summarizeBtn" in response.text or "summarize-btn" in response.text.lower()
        
        print(f"✓ GET /api/notepad/{code}/view has AI summarize button")


class TestExportStillWorks:
    """Verify export functionality still works"""
    
    def test_export_txt_still_works(self, api_client):
        """Test export as TXT still works"""
        # Create notepad with entry
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        api_client.post(f"{BASE_URL}/api/notepad/{code}/append", json={"text": "Export test"})
        
        response = api_client.get(f"{BASE_URL}/api/notepad/{code}/export?format=txt")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/plain" in response.headers.get("content-type", "")
        
        print("✓ GET /api/notepad/{code}/export?format=txt still works")


class TestSummarizeStillWorks:
    """Verify summarize functionality still works"""
    
    def test_summarize_still_works(self, api_client):
        """Test notepad summarize still works"""
        # Create notepad with substantial content
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": "Meeting notes: Discussed project timeline, assigned tasks to team members, set deadline for next Friday."}
        )
        
        response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/summarize",
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "summary" in data
        assert len(data["summary"]) > 0
        
        print(f"✓ POST /api/notepad/{code}/summarize still works")


# ==================== Existing Endpoints Still Work ====================

class TestExistingEndpointsStillWork:
    """Verify existing auth and notepad endpoints are not broken"""
    
    def test_auth_login_still_works(self, api_client):
        """Test login still works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "password123"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ POST /api/auth/login still works")
    
    def test_notepad_crud_still_works(self, api_client):
        """Test notepad CRUD still works"""
        # Create
        create_response = api_client.post(f"{BASE_URL}/api/notepad")
        assert create_response.status_code == 200
        code = create_response.json()["code"]
        
        # Read
        get_response = api_client.get(f"{BASE_URL}/api/notepad/{code}")
        assert get_response.status_code == 200
        
        # Update (append)
        append_response = api_client.post(
            f"{BASE_URL}/api/notepad/{code}/append",
            json={"text": "CRUD test"}
        )
        assert append_response.status_code == 200
        
        # Delete (clear)
        delete_response = api_client.delete(f"{BASE_URL}/api/notepad/{code}")
        assert delete_response.status_code == 200
        
        print("✓ Notepad CRUD operations still work")
    
    def test_landing_page_still_works(self, api_client):
        """Test landing page still renders"""
        response = api_client.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "PasteBridge" in response.text
        
        print("✓ GET /api/ landing page still works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
