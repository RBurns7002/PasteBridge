#!/usr/bin/env python3
"""
Backend API Testing for PasteBridge
Tests all notepad API endpoints
"""

import requests
import json
import time
from datetime import datetime
import sys

# Backend URL from frontend .env
BACKEND_URL = "https://clip-sync-1.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log_test(test_name, status, message=""):
    color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
    print(f"{color}[{status}]{Colors.ENDC} {test_name}")
    if message:
        print(f"    {message}")

def test_create_notepad():
    """Test POST /api/notepad - Create new notepad"""
    print(f"\n{Colors.BOLD}Testing: Create Notepad API{Colors.ENDC}")
    
    try:
        response = requests.post(f"{API_BASE}/notepad", timeout=10)
        
        if response.status_code != 200:
            log_test("Create Notepad", "FAIL", f"Expected status 200, got {response.status_code}")
            return None
            
        data = response.json()
        
        # Validate response structure
        required_fields = ['id', 'slug', 'entries', 'created_at', 'updated_at']
        for field in required_fields:
            if field not in data:
                log_test("Create Notepad", "FAIL", f"Missing field: {field}")
                return None
        
        # Validate data types
        if not isinstance(data['entries'], list):
            log_test("Create Notepad", "FAIL", "entries should be a list")
            return None
            
        if len(data['entries']) != 0:
            log_test("Create Notepad", "FAIL", "entries should be empty initially")
            return None
            
        if not data['slug'] or len(data['slug']) < 4:
            log_test("Create Notepad", "FAIL", "slug should be a non-empty string with reasonable length")
            return None
            
        log_test("Create Notepad", "PASS", f"Created notepad with slug: {data['slug']}")
        return data['slug']
        
    except requests.exceptions.RequestException as e:
        log_test("Create Notepad", "FAIL", f"Request failed: {str(e)}")
        return None
    except json.JSONDecodeError:
        log_test("Create Notepad", "FAIL", "Invalid JSON response")
        return None
    except Exception as e:
        log_test("Create Notepad", "FAIL", f"Unexpected error: {str(e)}")
        return None

def test_get_notepad(slug):
    """Test GET /api/notepad/{slug} - Get notepad by slug"""
    print(f"\n{Colors.BOLD}Testing: Get Notepad API{Colors.ENDC}")
    
    try:
        response = requests.get(f"{API_BASE}/notepad/{slug}", timeout=10)
        
        if response.status_code != 200:
            log_test("Get Notepad", "FAIL", f"Expected status 200, got {response.status_code}")
            return False
            
        data = response.json()
        
        # Validate response structure
        required_fields = ['id', 'slug', 'entries', 'created_at', 'updated_at']
        for field in required_fields:
            if field not in data:
                log_test("Get Notepad", "FAIL", f"Missing field: {field}")
                return False
        
        if data['slug'] != slug:
            log_test("Get Notepad", "FAIL", f"Expected slug {slug}, got {data['slug']}")
            return False
            
        log_test("Get Notepad", "PASS", f"Retrieved notepad with {len(data['entries'])} entries")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Get Notepad", "FAIL", f"Request failed: {str(e)}")
        return False
    except json.JSONDecodeError:
        log_test("Get Notepad", "FAIL", "Invalid JSON response")
        return False
    except Exception as e:
        log_test("Get Notepad", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_get_nonexistent_notepad():
    """Test GET /api/notepad/{slug} with non-existent slug"""
    print(f"\n{Colors.BOLD}Testing: Get Non-existent Notepad{Colors.ENDC}")
    
    try:
        fake_slug = "nonexistent123"
        response = requests.get(f"{API_BASE}/notepad/{fake_slug}", timeout=10)
        
        if response.status_code != 404:
            log_test("Get Non-existent Notepad", "FAIL", f"Expected status 404, got {response.status_code}")
            return False
            
        log_test("Get Non-existent Notepad", "PASS", "Correctly returned 404 for non-existent notepad")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Get Non-existent Notepad", "FAIL", f"Request failed: {str(e)}")
        return False
    except Exception as e:
        log_test("Get Non-existent Notepad", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_append_text(slug):
    """Test POST /api/notepad/{slug}/append - Append text to notepad"""
    print(f"\n{Colors.BOLD}Testing: Append Text API{Colors.ENDC}")
    
    test_texts = [
        "Hello from clipboard test!",
        "This is a second entry with special chars: @#$%^&*()",
        "Multi-line text\nwith newlines\nand more content"
    ]
    
    try:
        for i, text in enumerate(test_texts):
            payload = {"text": text}
            response = requests.post(f"{API_BASE}/notepad/{slug}/append", 
                                   json=payload, timeout=10)
            
            if response.status_code != 200:
                log_test(f"Append Text #{i+1}", "FAIL", f"Expected status 200, got {response.status_code}")
                return False
                
            data = response.json()
            
            # Validate response structure
            if 'entries' not in data:
                log_test(f"Append Text #{i+1}", "FAIL", "Missing entries field")
                return False
                
            if len(data['entries']) != i + 1:
                log_test(f"Append Text #{i+1}", "FAIL", f"Expected {i+1} entries, got {len(data['entries'])}")
                return False
                
            # Check if the latest entry matches what we sent
            latest_entry = data['entries'][-1]
            if latest_entry['text'] != text:
                log_test(f"Append Text #{i+1}", "FAIL", f"Text mismatch. Expected: {text}, Got: {latest_entry['text']}")
                return False
                
            # Check if timestamp exists
            if 'timestamp' not in latest_entry:
                log_test(f"Append Text #{i+1}", "FAIL", "Missing timestamp in entry")
                return False
                
            log_test(f"Append Text #{i+1}", "PASS", f"Successfully appended: {text[:50]}...")
            
            # Small delay between requests
            time.sleep(0.5)
        
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Append Text", "FAIL", f"Request failed: {str(e)}")
        return False
    except json.JSONDecodeError:
        log_test("Append Text", "FAIL", "Invalid JSON response")
        return False
    except Exception as e:
        log_test("Append Text", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_append_to_nonexistent_notepad():
    """Test POST /api/notepad/{slug}/append with non-existent slug"""
    print(f"\n{Colors.BOLD}Testing: Append to Non-existent Notepad{Colors.ENDC}")
    
    try:
        fake_slug = "nonexistent123"
        payload = {"text": "This should fail"}
        response = requests.post(f"{API_BASE}/notepad/{fake_slug}/append", 
                               json=payload, timeout=10)
        
        if response.status_code != 404:
            log_test("Append to Non-existent", "FAIL", f"Expected status 404, got {response.status_code}")
            return False
            
        log_test("Append to Non-existent", "PASS", "Correctly returned 404 for non-existent notepad")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Append to Non-existent", "FAIL", f"Request failed: {str(e)}")
        return False
    except Exception as e:
        log_test("Append to Non-existent", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_clear_notepad(slug):
    """Test DELETE /api/notepad/{slug} - Clear notepad entries"""
    print(f"\n{Colors.BOLD}Testing: Clear Notepad API{Colors.ENDC}")
    
    try:
        response = requests.delete(f"{API_BASE}/notepad/{slug}", timeout=10)
        
        if response.status_code != 200:
            log_test("Clear Notepad", "FAIL", f"Expected status 200, got {response.status_code}")
            return False
            
        data = response.json()
        
        if 'message' not in data:
            log_test("Clear Notepad", "FAIL", "Missing message field in response")
            return False
            
        # Verify notepad is actually cleared by getting it
        get_response = requests.get(f"{API_BASE}/notepad/{slug}", timeout=10)
        if get_response.status_code == 200:
            get_data = get_response.json()
            if len(get_data['entries']) != 0:
                log_test("Clear Notepad", "FAIL", f"Notepad not cleared, still has {len(get_data['entries'])} entries")
                return False
                
        log_test("Clear Notepad", "PASS", "Successfully cleared notepad entries")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Clear Notepad", "FAIL", f"Request failed: {str(e)}")
        return False
    except json.JSONDecodeError:
        log_test("Clear Notepad", "FAIL", "Invalid JSON response")
        return False
    except Exception as e:
        log_test("Clear Notepad", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_clear_nonexistent_notepad():
    """Test DELETE /api/notepad/{slug} with non-existent slug"""
    print(f"\n{Colors.BOLD}Testing: Clear Non-existent Notepad{Colors.ENDC}")
    
    try:
        fake_slug = "nonexistent123"
        response = requests.delete(f"{API_BASE}/notepad/{fake_slug}", timeout=10)
        
        if response.status_code != 404:
            log_test("Clear Non-existent", "FAIL", f"Expected status 404, got {response.status_code}")
            return False
            
        log_test("Clear Non-existent", "PASS", "Correctly returned 404 for non-existent notepad")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Clear Non-existent", "FAIL", f"Request failed: {str(e)}")
        return False
    except Exception as e:
        log_test("Clear Non-existent", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_html_view(slug):
    """Test GET /api/notepad/{slug}/view - Get HTML view"""
    print(f"\n{Colors.BOLD}Testing: HTML View API{Colors.ENDC}")
    
    try:
        response = requests.get(f"{API_BASE}/notepad/{slug}/view", timeout=10)
        
        if response.status_code != 200:
            log_test("HTML View", "FAIL", f"Expected status 200, got {response.status_code}")
            return False
            
        content = response.text
        
        # Validate HTML content (strip leading whitespace)
        content_stripped = content.strip()
        if not content_stripped.startswith('<!DOCTYPE html>'):
            log_test("HTML View", "FAIL", "Response is not valid HTML")
            return False
            
        # Check if slug is in the page
        if slug not in content:
            log_test("HTML View", "FAIL", f"Slug {slug} not found in HTML content")
            return False
            
        # Check for auto-refresh meta tag
        if 'http-equiv="refresh"' not in content:
            log_test("HTML View", "FAIL", "Auto-refresh meta tag not found")
            return False
            
        # Check for PasteBridge title
        if 'PasteBridge' not in content:
            log_test("HTML View", "FAIL", "PasteBridge title not found")
            return False
            
        log_test("HTML View", "PASS", f"Valid HTML page returned with slug {slug}")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("HTML View", "FAIL", f"Request failed: {str(e)}")
        return False
    except Exception as e:
        log_test("HTML View", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_html_view_nonexistent():
    """Test GET /api/notepad/{slug}/view with non-existent slug"""
    print(f"\n{Colors.BOLD}Testing: HTML View Non-existent{Colors.ENDC}")
    
    try:
        fake_slug = "nonexistent123"
        response = requests.get(f"{API_BASE}/notepad/{fake_slug}/view", timeout=10)
        
        if response.status_code != 404:
            log_test("HTML View Non-existent", "FAIL", f"Expected status 404, got {response.status_code}")
            return False
            
        content = response.text
        if "not found" not in content.lower():
            log_test("HTML View Non-existent", "FAIL", "404 page doesn't contain 'not found' message")
            return False
            
        log_test("HTML View Non-existent", "PASS", "Correctly returned 404 HTML for non-existent notepad")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("HTML View Non-existent", "FAIL", f"Request failed: {str(e)}")
        return False
    except Exception as e:
        log_test("HTML View Non-existent", "FAIL", f"Unexpected error: {str(e)}")
        return False

def test_health_check():
    """Test GET /api/ - Health check"""
    print(f"\n{Colors.BOLD}Testing: Health Check API{Colors.ENDC}")
    
    try:
        response = requests.get(f"{API_BASE}/", timeout=10)
        
        if response.status_code != 200:
            log_test("Health Check", "FAIL", f"Expected status 200, got {response.status_code}")
            return False
            
        data = response.json()
        
        if 'message' not in data:
            log_test("Health Check", "FAIL", "Missing message field")
            return False
            
        log_test("Health Check", "PASS", f"API is running: {data['message']}")
        return True
        
    except requests.exceptions.RequestException as e:
        log_test("Health Check", "FAIL", f"Request failed: {str(e)}")
        return False
    except json.JSONDecodeError:
        log_test("Health Check", "FAIL", "Invalid JSON response")
        return False
    except Exception as e:
        log_test("Health Check", "FAIL", f"Unexpected error: {str(e)}")
        return False

def run_full_test_suite():
    """Run complete test suite"""
    print(f"{Colors.BOLD}{'='*60}")
    print("PasteBridge Backend API Test Suite")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"{'='*60}{Colors.ENDC}")
    
    test_results = []
    
    # Health check first
    test_results.append(test_health_check())
    
    # Create a notepad for testing
    slug = test_create_notepad()
    if not slug:
        print(f"\n{Colors.RED}CRITICAL: Cannot create notepad. Stopping tests.{Colors.ENDC}")
        return False
    
    test_results.append(True)  # Create notepad passed
    
    # Test getting the notepad
    test_results.append(test_get_notepad(slug))
    
    # Test error handling for non-existent notepad
    test_results.append(test_get_nonexistent_notepad())
    
    # Test appending text
    test_results.append(test_append_text(slug))
    
    # Test error handling for append to non-existent
    test_results.append(test_append_to_nonexistent_notepad())
    
    # Test HTML view with entries
    test_results.append(test_html_view(slug))
    
    # Test HTML view error handling
    test_results.append(test_html_view_nonexistent())
    
    # Test clearing notepad
    test_results.append(test_clear_notepad(slug))
    
    # Test error handling for clear non-existent
    test_results.append(test_clear_nonexistent_notepad())
    
    # Final HTML view test (should show empty)
    test_results.append(test_html_view(slug))
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n{Colors.BOLD}{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}{Colors.ENDC}")
    
    if passed == total:
        print(f"{Colors.GREEN}✅ ALL TESTS PASSED ({passed}/{total}){Colors.ENDC}")
        return True
    else:
        print(f"{Colors.RED}❌ SOME TESTS FAILED ({passed}/{total}){Colors.ENDC}")
        return False

if __name__ == "__main__":
    success = run_full_test_suite()
    sys.exit(0 if success else 1)