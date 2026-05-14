3#!/usr/bin/env python3
"""
Standalone Flask OAuth Authentication Server
Handles Strava OAuth callbacks and saves tokens to JSON file
"""

import json
import os
import subprocess
from flask import Flask, request

from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET

# Get token file path from environment variable, default to global.json
TOKEN_FILE_PATH = os.getenv('TOKEN_FILE_PATH', 'global.json')

app = Flask('strava_auth')

@app.route('/', methods=['POST', 'GET'])
def authorization_successful():
    """Handle OAuth callback from Strava"""
    authorization_code = request.args.get('code')

    if authorization_code:
        print(f'Got authorization code: {authorization_code}')

        # Exchange code for access token using curl
        curl_command = [
            "curl",
            "-X", "POST",
            f"https://www.strava.com/api/v3/oauth/token?"
            f"client_id={APP_CLIENT_ID}&"
            f"client_secret={APP_CLIENT_SECRET}&"
            f"code={authorization_code}&"
            f"grant_type=authorization_code"
        ]

        try:
            result = subprocess.run(curl_command, capture_output=True, text=True, check=True)
            response_data = json.loads(result.stdout)

            access_token = response_data['access_token']
            print(f'Received access token: {access_token}')

            # Save to configured token file
            session_data = {
                'token': access_token,
                'athlete': response_data['athlete']
            }

            with open(TOKEN_FILE_PATH, "w") as outfile:
                json.dump(session_data, outfile, indent=2)

            print(f'Token saved to {TOKEN_FILE_PATH}')
            return "Authorization successful! You can close this tab now."

        except subprocess.CalledProcessError as e:
            print(f'Error exchanging code for token: {e.stderr}')
            return f"Authorization failed: {e.stderr}", 500
        except Exception as e:
            print(f'Unexpected error: {e}')
            return f"Authorization failed: {str(e)}", 500
    else:
        return "Authorization failed: No code provided.", 400

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'service': 'strava-auth'}, 200

if __name__ == '__main__':
    print('Starting Strava OAuth Authentication Server...')
    print('Listening on http://0.0.0.0:3476')
    print(f'Token will be saved to: {TOKEN_FILE_PATH}')
    app.run(host='0.0.0.0', port=3476, debug=False)