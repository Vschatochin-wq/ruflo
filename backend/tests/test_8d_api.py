"""
8D-Opus Reklamationsmanagement API Tests
=========================================
Tests for all backend API endpoints:
- Health check
- Complaints CRUD
- Statistics
- Notifications
- Reviews
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthCheck:
    """Health endpoint tests"""
    
    def test_health_returns_ok(self):
        """Test /api/health returns status ok with database connected"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert "service" in data
        print(f"✓ Health check passed: {data}")


class TestComplaints:
    """Complaints CRUD endpoint tests"""
    
    def test_list_complaints_returns_seeded_data(self):
        """Test /api/v1/complaints returns list of 3 seeded complaints"""
        response = requests.get(f"{BASE_URL}/api/v1/complaints")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "complaints" in data
        items = data.get("items") or data.get("complaints", [])
        assert len(items) >= 3, f"Expected at least 3 complaints, got {len(items)}"
        print(f"✓ Complaints list returned {len(items)} items")
        
        # Verify seeded customers exist
        customer_names = [c.get("customer_name") for c in items]
        assert "BMW AG" in customer_names, "BMW AG not found in complaints"
        assert "Daimler AG" in customer_names, "Daimler AG not found in complaints"
        assert "Volkswagen AG" in customer_names, "Volkswagen AG not found in complaints"
        print("✓ All seeded customers found: BMW AG, Daimler AG, Volkswagen AG")
    
    def test_get_complaint_by_id(self):
        """Test getting a single complaint by ID"""
        # First get list to find an ID
        list_response = requests.get(f"{BASE_URL}/api/v1/complaints")
        assert list_response.status_code == 200
        items = list_response.json().get("items") or list_response.json().get("complaints", [])
        assert len(items) > 0
        
        complaint_id = items[0]["id"]
        response = requests.get(f"{BASE_URL}/api/v1/complaints/{complaint_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == complaint_id
        print(f"✓ Got complaint detail for ID: {complaint_id}")
    
    def test_complaint_summary(self):
        """Test complaint summary endpoint"""
        # Get a complaint ID first
        list_response = requests.get(f"{BASE_URL}/api/v1/complaints")
        items = list_response.json().get("items") or list_response.json().get("complaints", [])
        complaint_id = items[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/v1/complaints/{complaint_id}/summary")
        assert response.status_code == 200
        print(f"✓ Complaint summary endpoint works")
    
    def test_complaint_allowed_transitions(self):
        """Test allowed transitions endpoint"""
        list_response = requests.get(f"{BASE_URL}/api/v1/complaints")
        items = list_response.json().get("items") or list_response.json().get("complaints", [])
        complaint_id = items[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/v1/complaints/{complaint_id}/allowed-transitions")
        assert response.status_code == 200
        data = response.json()
        assert "transitions" in data
        print(f"✓ Allowed transitions endpoint works")


class TestStatistics:
    """Statistics endpoint tests"""
    
    def test_dashboard_statistics(self):
        """Test /api/v1/statistics/dashboard returns dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/dashboard")
        assert response.status_code == 200
        data = response.json()
        # Check expected fields
        assert "total_complaints" in data or "open_complaints" in data
        print(f"✓ Dashboard statistics: {data}")
    
    def test_status_distribution(self):
        """Test status distribution endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/status-distribution")
        assert response.status_code == 200
        data = response.json()
        assert "distribution" in data
        print(f"✓ Status distribution endpoint works")
    
    def test_trends(self):
        """Test trends endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/trends")
        assert response.status_code == 200
        data = response.json()
        assert "trends" in data
        print(f"✓ Trends endpoint works")
    
    def test_top_errors(self):
        """Test top errors endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/top-errors")
        assert response.status_code == 200
        data = response.json()
        assert "error_codes" in data
        print(f"✓ Top errors endpoint works")
    
    def test_top_customers(self):
        """Test top customers endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/top-customers")
        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        print(f"✓ Top customers endpoint works")
    
    def test_score_distribution(self):
        """Test score distribution endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/score-distribution")
        assert response.status_code == 200
        print(f"✓ Score distribution endpoint works")
    
    def test_processing_time(self):
        """Test processing time endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/processing-time")
        assert response.status_code == 200
        print(f"✓ Processing time endpoint works")
    
    def test_error_locations(self):
        """Test error locations endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/error-locations")
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        print(f"✓ Error locations endpoint works")
    
    def test_monthly_statistics(self):
        """Test monthly statistics endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/statistics/monthly")
        assert response.status_code == 200
        data = response.json()
        assert "months" in data
        print(f"✓ Monthly statistics endpoint works")


class TestNotifications:
    """Notification endpoint tests"""
    
    def test_list_notifications(self):
        """Test /api/v1/notifications returns notifications array"""
        response = requests.get(f"{BASE_URL}/api/v1/notifications")
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert isinstance(data["notifications"], list)
        print(f"✓ Notifications list returned {len(data['notifications'])} items")
    
    def test_unread_count(self):
        """Test /api/v1/notifications/unread-count returns count"""
        response = requests.get(f"{BASE_URL}/api/v1/notifications/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert "unread_count" in data
        assert isinstance(data["unread_count"], int)
        print(f"✓ Unread count: {data['unread_count']}")


class TestReviews:
    """Review endpoint tests"""
    
    def test_review_queue(self):
        """Test /api/v1/reviews/queue returns queue"""
        response = requests.get(f"{BASE_URL}/api/v1/reviews/queue")
        assert response.status_code == 200
        data = response.json()
        assert "queue" in data
        assert "count" in data
        print(f"✓ Review queue returned {data['count']} items")
    
    def test_review_statistics(self):
        """Test /api/v1/reviews/statistics returns stats"""
        response = requests.get(f"{BASE_URL}/api/v1/reviews/statistics")
        assert response.status_code == 200
        print(f"✓ Review statistics endpoint works")
    
    def test_pending_reviews(self):
        """Test /api/v1/reviews/pending returns pending reviews"""
        response = requests.get(f"{BASE_URL}/api/v1/reviews/pending")
        assert response.status_code == 200
        data = response.json()
        assert "pending" in data
        print(f"✓ Pending reviews endpoint works")


class TestComplaintCRUD:
    """Test complaint create, update, delete operations"""
    
    def test_create_complaint(self):
        """Test creating a new complaint"""
        payload = {
            "customer_name": "TEST_AutoTest GmbH",
            "problem_description": "Test complaint created by automated testing",
            "message_type": "Q3"
        }
        response = requests.post(f"{BASE_URL}/api/v1/complaints", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["customer_name"] == "TEST_AutoTest GmbH"
        print(f"✓ Created complaint with ID: {data['id']}")
        
        # Verify by GET
        get_response = requests.get(f"{BASE_URL}/api/v1/complaints/{data['id']}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["customer_name"] == "TEST_AutoTest GmbH"
        print(f"✓ Verified complaint creation via GET")
        
        return data["id"]
    
    def test_update_complaint(self):
        """Test updating a complaint"""
        # Create first
        create_payload = {
            "customer_name": "TEST_UpdateTest GmbH",
            "problem_description": "Original description"
        }
        create_response = requests.post(f"{BASE_URL}/api/v1/complaints", json=create_payload)
        assert create_response.status_code == 200
        complaint_id = create_response.json()["id"]
        
        # Update
        update_payload = {
            "problem_description": "Updated description by test"
        }
        update_response = requests.patch(f"{BASE_URL}/api/v1/complaints/{complaint_id}", json=update_payload)
        assert update_response.status_code == 200
        
        # Verify update
        get_response = requests.get(f"{BASE_URL}/api/v1/complaints/{complaint_id}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["problem_description"] == "Updated description by test"
        print(f"✓ Updated and verified complaint: {complaint_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
