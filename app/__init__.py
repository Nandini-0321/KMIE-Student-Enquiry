"""
Application Factory for KMIE Student Enquiry & Demo Booking System.
"""
import logging
import os
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from app.config import config_by_name
from app.extensions import csrf
from app.services.supabase_service import supabase_service
from app.services.google_sheets_service import google_sheets_service

# Setup structured logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("kmie_app")


def create_app(config_name: str = None) -> Flask:
    """Application factory for Flask web application."""
    if config_name is None:
        config_name = os.getenv("APP_ENV", "development").lower()

    app = Flask(__name__)
    config_class = config_by_name.get(config_name, config_by_name["development"])
    app.config.from_object(config_class)

    # Initialize extensions
    csrf.init_app(app)

    # Register blueprints
    from app.routes.public import public_bp
    from app.routes.booking import booking_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)

    # -------------------------------------------------------------------------
    # Health Check Endpoints
    # -------------------------------------------------------------------------
    @app.route("/health/live", methods=["GET"])
    def health_live():
        """Liveness check confirming the HTTP web server process is running."""
        return jsonify({
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    @app.route("/health/ready", methods=["GET"])
    def health_ready():
        """Readiness check verifying database connectivity and integration status."""
        db_ok, db_msg = supabase_service.check_connection()
        sheets_ok, sheets_msg = google_sheets_service.check_connection()

        readiness = {
            "status": "ready" if db_ok else "unhealthy",
            "database": {
                "connected": db_ok,
                "message": "Connected" if db_ok else db_msg,
            },
            "google_sheets": {
                "configured": google_sheets_service.is_configured(),
                "connected": sheets_ok,
                "message": "Connected" if sheets_ok else sheets_msg,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # If database is down, system is not ready
        if not db_ok:
            return jsonify(readiness), 503

        # If database is up but Sheets is degraded, app is still functional for saving enquiries
        if not sheets_ok:
            readiness["status"] = "degraded"

        return jsonify(readiness), 200

    # -------------------------------------------------------------------------
    # Security Headers Hook
    # -------------------------------------------------------------------------
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # -------------------------------------------------------------------------
    # Template Context Processors
    # -------------------------------------------------------------------------
    @app.context_processor
    def inject_global_template_vars():
        return {
            "app_name": "KMIE Excellence Automation",
            "current_year": datetime.now().year,
        }

    # -------------------------------------------------------------------------
    # Error Handlers
    # -------------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request_error(err):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "Bad request", "details": str(err)}), 400
        return render_template("errors/400.html", message=str(err)), 400

    @app.errorhandler(404)
    def not_found_error(err):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(CSRFError)
    def handle_csrf_error(err):
        logger.warning("CSRF validation failure from %s", request.remote_addr)
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "CSRF token missing or invalid"}), 400
        return render_template(
            "errors/400.html",
            message="Your session or form security token has expired. Please refresh the page and try again.",
        ), 400

    @app.errorhandler(500)
    def internal_server_error(err):
        logger.error("Internal Server Error: %s", err, exc_info=True)
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    return app
