"""
Constants for authorization server
Self-contained - no external dependencies
"""

import os

# Strava OAuth credentials
APP_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
APP_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")

# Server configuration
AUTH_SERVER_HOST = '0.0.0.0'
AUTH_SERVER_PORT = 3476
