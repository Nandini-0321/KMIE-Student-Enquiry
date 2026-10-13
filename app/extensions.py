"""
Flask extensions initialization.
"""
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
