"""
WSGI Entry Point for KMIE Student Enquiry & Demo Booking System.
Used by Gunicorn in production (gunicorn wsgi:app) and local development.
"""
import os
from app import create_app

env_name = os.getenv("APP_ENV", "development").lower()
app = create_app(env_name)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug_mode = os.getenv("DEBUG", "False").lower() in ("true", "1")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
