import json
import os
import subprocess
from flask import Flask, request

from auth_constants import APP_CLIENT_ID, APP_CLIENT_SECRET, AUTH_SERVER_HOST, AUTH_SERVER_PORT

# Get token file path from environment variable, default to global.json
TOKEN_FILE_PATH = os.getenv('TOKEN_FILE_PATH', 'global.json')

flask_app = Flask('auth')

@flask_app.route('/' ,methods = ['POST', 'GET'])
def authorization_successful():
    authorization_code = request.args.get('code')
    if authorization_code:
        print(f'Got authorization code: {authorization_code}')
        # Save the code to the global session
        data = {
            "client_id": APP_CLIENT_ID,
            "client_secret": APP_CLIENT_SECRET,
            "code": authorization_code,
            "grant_type": "authorization_code"
        }
        print(f'posting: {data}')
        import subprocess

        # Define the curl command
        curl_command = [
            "curl",
            "-X", "POST",
            f"https://www.strava.com/api/v3/oauth/token?client_id={APP_CLIENT_ID}&client_secret={APP_CLIENT_SECRET}&code={authorization_code}&grant_type=authorization_code"
        ]
        result = subprocess.run(curl_command, capture_output=True, text=True, check=True)
        response_data = json.loads(result.stdout)
        STRAVA_ACCESS_TOKEN = response_data['access_token']
        print(f' Received access token: {STRAVA_ACCESS_TOKEN}')
        global_session = {
            'token': STRAVA_ACCESS_TOKEN,
            'athlete': response_data['athlete']
        }
        with open(TOKEN_FILE_PATH, "w") as outfile:
            json.dump(global_session, outfile, indent=2)
        print(f'Token saved to {TOKEN_FILE_PATH}')
        return "Authorization successful! You can close this tab now."
    else:
        return "Authorization failed.", 400

@flask_app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'service': 'strava-auth'}, 200

def run_flask_app():
    flask_app.run(host=AUTH_SERVER_HOST, port=AUTH_SERVER_PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    print('Starting Strava OAuth Authentication Server...')
    print(f'Listening on http://{AUTH_SERVER_HOST}:{AUTH_SERVER_PORT}')
    print(f'Token will be saved to: {TOKEN_FILE_PATH}')
    run_flask_app()
