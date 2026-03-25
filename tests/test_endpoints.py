"""
Integration tests for FastAPI endpoints.
Tests all CRUD operations and error cases.
"""

import pytest
from fastapi.testclient import TestClient


class TestRootEndpoint:
    """Tests for GET /"""
    
    def test_root_redirects_to_static_index(self, client):
        """Verify root path redirects to /static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivitiesEndpoint:
    """Tests for GET /activities"""
    
    def test_get_activities_returns_dict(self, client, fresh_activities):
        """Verify endpoint returns the activities dictionary"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) == 3
    
    def test_get_activities_contains_expected_fields(self, client, fresh_activities):
        """Verify each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity in data.items():
            assert "description" in activity
            assert "schedule" in activity
            assert "max_participants" in activity
            assert "participants" in activity
            assert isinstance(activity["participants"], list)
    
    def test_get_activities_returns_fresh_data(self, client, fresh_activities):
        """Verify endpoint returns the test fixture data"""
        response = client.get("/activities")
        data = response.json()
        
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert "Gym Class" in data


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup"""
    
    def test_signup_success_new_participant(self, client, fresh_activities):
        """Verify successful signup of new participant"""
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "alice@mergington.edu"}
        )
        assert response.status_code == 200
        assert "signed up" in response.json()["message"].lower()
        
        # Verify participant was added
        activities_response = client.get("/activities")
        chess_club = activities_response.json()["Chess Club"]
        assert "alice@mergington.edu" in chess_club["participants"]
    
    def test_signup_activity_not_found(self, client, fresh_activities):
        """Verify signup fails with 404 for non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Activity/signup",
            params={"email": "alice@mergington.edu"}
        )
        assert response.status_code == 404
        assert "activity not found" in response.json()["detail"].lower()
    
    def test_signup_duplicate_email(self, client, fresh_activities):
        """Verify signup fails with 400 for already registered student"""
        # michael@mergington.edu is already in Chess Club
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "michael@mergington.edu"}
        )
        assert response.status_code == 400
        assert "already signed up" in response.json()["detail"].lower()
    
    def test_signup_same_email_different_activity(self, client, fresh_activities):
        """Verify same student can signup for multiple activities"""
        response = client.post(
            "/activities/Programming Class/signup",
            params={"email": "michael@mergington.edu"}
        )
        assert response.status_code == 200
        
        # Verify added to second activity
        activities_response = client.get("/activities")
        prog_class = activities_response.json()["Programming Class"]
        assert "michael@mergington.edu" in prog_class["participants"]
    
    def test_signup_at_max_capacity(self, client, fresh_activities):
        """Verify signup succeeds even at max capacity (no capacity check yet)"""
        # Gym Class has max_participants=2 and 1 current participant (john@mergington.edu)
        # Add one more to reach capacity
        response1 = client.post(
            "/activities/Gym Class/signup",
            params={"email": "alice@mergington.edu"}
        )
        assert response1.status_code == 200
        
        # Add another - this demonstrates the app doesn't check capacity yet
        response2 = client.post(
            "/activities/Gym Class/signup",
            params={"email": "bob@mergington.edu"}
        )
        assert response2.status_code == 200
        
        # Verify all three are in the participants list
        activities_response = client.get("/activities")
        gym_class = activities_response.json()["Gym Class"]
        assert len(gym_class["participants"]) == 3  # Over capacity!


class TestUnregisterEndpoint:
    """Tests for DELETE /activities/{activity_name}/unregister"""
    
    def test_unregister_success(self, client, fresh_activities):
        """Verify successful removal of participant"""
        response = client.delete(
            "/activities/Chess Club/unregister",
            params={"email": "michael@mergington.edu"}
        )
        assert response.status_code == 200
        assert "unregistered" in response.json()["message"].lower()
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        chess_club = activities_response.json()["Chess Club"]
        assert "michael@mergington.edu" not in chess_club["participants"]
    
    def test_unregister_activity_not_found(self, client, fresh_activities):
        """Verify unregister fails with 404 for non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent Activity/unregister",
            params={"email": "alice@mergington.edu"}
        )
        assert response.status_code == 404
        assert "activity not found" in response.json()["detail"].lower()
    
    def test_unregister_student_not_registered(self, client, fresh_activities):
        """Verify unregister fails with 400 for student not in activity"""
        response = client.delete(
            "/activities/Chess Club/unregister",
            params={"email": "alice@mergington.edu"}
        )
        assert response.status_code == 400
        assert "not registered" in response.json()["detail"].lower()
    
    def test_unregister_all_participants_then_readd(self, client, fresh_activities):
        """Verify can remove all participants and then re-add them"""
        # Remove both participants from Chess Club
        client.delete(
            "/activities/Chess Club/unregister",
            params={"email": "michael@mergington.edu"}
        )
        client.delete(
            "/activities/Chess Club/unregister",
            params={"email": "daniel@mergington.edu"}
        )
        
        # Verify empty
        activities_response = client.get("/activities")
        chess_club = activities_response.json()["Chess Club"]
        assert len(chess_club["participants"]) == 0
        
        # Re-signup one
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "michael@mergington.edu"}
        )
        assert response.status_code == 200
        
        # Verify added back
        activities_response = client.get("/activities")
        chess_club = activities_response.json()["Chess Club"]
        assert "michael@mergington.edu" in chess_club["participants"]
        assert len(chess_club["participants"]) == 1


class TestEndpointIntegration:
    """Integration tests combining multiple endpoints"""
    
    def test_full_signup_and_unregister_flow(self, client, fresh_activities):
        """Verify complete user flow: view activities -> signup -> unregister"""
        # 1. View all activities
        response = client.get("/activities")
        assert response.status_code == 200
        activities = response.json()
        assert "Programming Class" in activities
        
        # 2. Signup for activity
        response = client.post(
            "/activities/Programming Class/signup",
            params={"email": "newstudent@mergington.edu"}
        )
        assert response.status_code == 200
        
        # 3. Verify participant appears in activities list
        response = client.get("/activities")
        prog_class = response.json()["Programming Class"]
        assert "newstudent@mergington.edu" in prog_class["participants"]
        
        # 4. Unregister from activity
        response = client.delete(
            "/activities/Programming Class/unregister",
            params={"email": "newstudent@mergington.edu"}
        )
        assert response.status_code == 200
        
        # 5. Verify participant is removed
        response = client.get("/activities")
        prog_class = response.json()["Programming Class"]
        assert "newstudent@mergington.edu" not in prog_class["participants"]
    
    def test_multiple_signups_and_signups_different_activities(self, client, fresh_activities):
        """Verify one student can signup for multiple activities"""
        student_email = "superactive@mergington.edu"
        activities = ["Chess Club", "Programming Class", "Gym Class"]
        
        # Signup for all three
        for activity in activities:
            response = client.post(
                f"/activities/{activity}/signup",
                params={"email": student_email}
            )
            assert response.status_code == 200
        
        # Verify student is in all three
        response = client.get("/activities")
        data = response.json()
        for activity in activities:
            assert student_email in data[activity]["participants"]
        
        # Unregister from one
        client.delete(
            "/activities/Chess Club/unregister",
            params={"email": student_email}
        )
        
        # Verify removed from only that activity
        response = client.get("/activities")
        data = response.json()
        assert student_email not in data["Chess Club"]["participants"]
        assert student_email in data["Programming Class"]["participants"]
        assert student_email in data["Gym Class"]["participants"]
