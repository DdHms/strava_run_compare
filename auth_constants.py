"""
Minimal constants for auth server only
Avoids importing numpy and other heavy dependencies
"""

import os

# Strava OAuth credentials
APP_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
APP_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
