"""
Tests for Admin Security, Authentication, Authorization, and Health Check Endpoints.
Verifies Requirements:
- 18. Unauthorized admin access protection
- 20. Health-check endpoint behavior
"""
import pytest
from unittest.mock import MagicMock
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service


class TestAdminSecurityAndHealth:
    """Test suite for security barriers and system health."""

    def test_unauthorized_admin_access_redirect(self, client):
        """
        18. Verifies that unauthenticated access to admin dashboard redirects to login
        and does not leak private records.
        """
        resp = client.get("/admin/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_unauthorized_state_mutation_blocked(self, client):
        """
        18. Verifies that unauthenticated state-changing POST requests are redirected/blocked.
        """
        # Attempt to change booking status without auth
        resp = client.post("/admin/bookings/any-id/status", data={"status": "Attended"}, follow_redirects=False)
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

        # Attempt to retry sync without auth
        resp2 = client.post("/admin/sync/retry/lead/any-id", follow_redirects=False)
        assert resp2.status_code == 302
        assert "/admin/login" in resp2.headers["Location"]

    def test_authenticated_admin_access(self, auth_client, mock_supabase):
        """Verifies that an authenticated admin can access the dashboard."""
        resp = auth_client.get("/admin/dashboard")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Admissions &amp; Bookings Management" in html

    def test_health_live_endpoint(self, client):
        """20. Verifies /health/live returns HTTP 200 and alive status."""
        resp = client.get("/health/live")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_health_ready_endpoint_healthy(self, client, monkeypatch):
        """20. Verifies /health/ready returns status ready when database and sheets are connected."""
        monkeypatch.setattr(supabase_service, "check_connection", lambda: (True, "Connected"))
        monkeypatch.setattr(google_sheets_service, "is_configured", lambda: True)
        monkeypatch.setattr(google_sheets_service, "check_connection", lambda: (True, "Connected"))

        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ready"
        assert data["database"]["connected"] is True
        assert data["google_sheets"]["connected"] is True

    def test_health_ready_endpoint_degraded(self, client, monkeypatch):
        """
        20. Verifies /health/ready reports degraded (not unhealthy 503) if database is up
        but Google Sheets is temporarily unreachable.
        """
        monkeypatch.setattr(supabase_service, "check_connection", lambda: (True, "Connected"))
        monkeypatch.setattr(google_sheets_service, "is_configured", lambda: True)
        monkeypatch.setattr(google_sheets_service, "check_connection", lambda: (False, "Sheets API unavailable"))

        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "degraded"
        assert data["database"]["connected"] is True
        assert data["google_sheets"]["connected"] is False

    def test_health_ready_endpoint_database_down(self, client, monkeypatch):
        """20. Verifies /health/ready returns 503 when the primary database is unreachable."""
        monkeypatch.setattr(supabase_service, "check_connection", lambda: (False, "Supabase unreachable"))

        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "unhealthy"
        assert data["database"]["connected"] is False
