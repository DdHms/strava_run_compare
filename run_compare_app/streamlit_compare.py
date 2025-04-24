import json
import socket
import sys
import threading

import pandas as pd
import requests
import streamlit as st
from flask import Flask
from flask import request
from streamlit_oauth import OAuth2Component

from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET, N_ACTIVITIES, \
    REVOKE_TOKEN_URL, REFRESH_TOKEN_URL, TOKEN_URL, AUTHORIZE_URL, SCOPE, REDIRECT_URI
from run_compare.prompt_constants import SUGGESTED_EXERCISE_PROMPT, SYSTEM_PROMPT, ai_schema_type_json
from run_compare.strava_api_utils import get_activities
from run_compare.stravaio import StravaIO
from run_compare.visualisation_utils import plot_to_date, speed_to_pace, distance_display
from run_compare_app.compare import collect_data_for_fig

sys.path.insert(0, '/home/hms/local_llm_server')
from llm_server.app import main as llm_server_main

# Global session management
session_ready = threading.Event()

st.set_page_config(
    page_title="Run compare",              # Title in browser tab
    page_icon="static/styles/logo.ico",     # Local image OR emoji OR URL
    # layout="centered",                # or "wide"
    # initial_sidebar_state="auto"
)

flask_app = Flask('auth')
flask_port = 3476  # Choose a port that's likely to be free

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
        global_session = {}
        global_session['token'] = STRAVA_ACCESS_TOKEN
        global_session['athlete'] = response_data['athlete']
        dumps = json.dumps(global_session)
        with open("global.json", "w") as outfile:
            outfile.write(dumps)
        session_ready.set()  # Signal that the code is ready
        return "Authorization successful! You can close this tab now."
    else:
        return "Authorization failed.", 400

def run_flask_app():
    flask_app.run(port=flask_port, debug=False, use_reloader=False)



def convert_activities_to_df(base_activities, inteval_activities):
    base_df = pd.DataFrame(base_activities)
    intervals_df = pd.DataFrame(inteval_activities)

    base_df['source'] = 'base_activity'
    intervals_df['source'] = 'interval'

    base_df.rename(columns={'SPEED': 'BASE_SPEED', 'DISTANCE': 'BASE_DISTANCE', 'HR': 'BASE_HR'}, inplace=True)
    intervals_df.rename(columns={'INTERVAL_SPEED': 'INTERVAL_SPEED', 'INTERVAL_DISTANCE': 'INTERVAL_DISTANCE',
                                 'INTERVAL_HR': 'INTERVAL_HR'}, inplace=True)

    combined_df = pd.concat([base_df, intervals_df], ignore_index=True).sort_values(by='date').reset_index(drop=True)

    def format_distance(row):
        if row['source'] == 'base_activity':
            return distance_display(row['BASE_DISTANCE'])
        elif row['source'] == 'interval':
            return f"{int(row['N_INTERVALS'])} X {distance_display(row['INTERVAL_DISTANCE'])}"

    def format_hr(row):
        return int(row['BASE_HR']) if row['source'] == 'base_activity' else int(row['INTERVAL_HR'])

    def format_speed(row):
        return speed_to_pace(row['BASE_SPEED']) if row['source'] == 'base_activity' else speed_to_pace(row['INTERVAL_SPEED'])

    formatted_df = pd.DataFrame({
        'date': combined_df['date'].apply(lambda x: x.strftime("%d/%m/%Y")),
        'source': combined_df['source'],
        'distance': combined_df.apply(format_distance, axis=1),
        'HR': combined_df.apply(format_hr, axis=1),
        'pace': combined_df.apply(format_speed, axis=1),
    })

    return formatted_df


def main():
    global_session = {}
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    ai_thread = threading.Thread(target=llm_server_main, daemon=True)
    with st.spinner("Starting AI server..."):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        not_open = sock.connect_ex(('127.0.0.1', 3888))
        if not_open:
            ai_thread.start()

    with st.spinner("Starting authorization server..."):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        not_open = sock.connect_ex(('127.0.0.1', flask_port))
        if not_open:
            flask_thread.start()
    st.title("Run Compare App")
    activities_tab, graph_tab, ai_tab = st.tabs(tabs=['Activities', 'Graph', 'AI trainer'])
    oauth2 = OAuth2Component(APP_CLIENT_ID, APP_CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, REFRESH_TOKEN_URL,
                             REVOKE_TOKEN_URL)
    with st.sidebar:
        result = oauth2.authorize_button("Authorize", REDIRECT_URI, SCOPE)
    while 'token' not in global_session:
        try:
            with open('global.json', 'r') as openfile:
                # Reading from json file
                global_session = json.load(openfile)
        except:
            pass
    STRAVA_ACCESS_TOKEN = st.session_state['strava_access_token'] = global_session['token']
    client = StravaIO(access_token=STRAVA_ACCESS_TOKEN)
    athlete = global_session['athlete']
    if athlete is not None:
        st.sidebar.write(f"Logged in as {athlete['firstname']} {athlete['lastname']}")

        with st.spinner("Downloading activities..."):
            non_summarized, full_run_activities = get_activities(access_token=STRAVA_ACCESS_TOKEN,
                                                                 invalidate_history=False,
                                                                 num_activities=N_ACTIVITIES)
        with st.spinner("Analyzing activities..."):
            for activity in non_summarized:
                calculate_analysis(activity_id=activity['id'], access_token=STRAVA_ACCESS_TOKEN)

            base_activities, interval_activities = gather_data_for_plotting(activity_list=full_run_activities)

        with graph_tab:
            st.write("## Activity Graph")
            fig_data = collect_data_for_fig(base_activities, interval_activities)

            fig = plot_to_date(fig_data['all_dates'], fig_data['all_speeds'], fig_data['all_dspeeds'],
                               color='rgba(0,100,255,',
                               name='Speed [min/km]', label=fig_data['all_labels'], marker_col=fig_data['all_marker_col'])
            fig = plot_to_date(fig_data['all_dates'], fig_data['all_hr'], fig_data['all_dhr'], color='rgba(255,100,0,',
                               name='HR [BPM]', label=[f'{int(hr)}\U0001fac0' for hr in fig_data['all_hr']], add_to_fig=fig,
                               separate=True)

            # display df.html as an html component:

            st.plotly_chart(fig)
        with activities_tab:
            st.write("Show Activities Table")
            df = convert_activities_to_df(base_activities, interval_activities)
            st.dataframe(df)
        with ai_tab:
            st.write("Ask AI")
            df = convert_activities_to_df(base_activities, interval_activities)
            data = df.to_dict(orient='index')
            request = {'user_prompt': SUGGESTED_EXERCISE_PROMPT,
                       'system_prompt': SYSTEM_PROMPT,
                       'schema': ai_schema_type_json,
                       'context': data}

            response = requests.post('http://localhost:3888/generate', json=request)
            json_response = response.json()
            st.write('### Overall Progress:')
            chat_answer = json.loads(json_response['response'])
            st.write(chat_answer['progress'])
            st.write('### Next AI Suggested Run:')
            exercise_type = chat_answer['next_suggested_run']['type']
            st.write(f'#### {exercise_type}')
            for exercise in chat_answer['next_suggested_run']['plan']:
                ln = f"{exercise['repetitions']} X {exercise['distance']}m @ {exercise['target_pace']} min/km, {exercise['target_heart_rate']} BPM rest time: {exercise['rest_time']} min \n"
                st.write(ln)
if __name__ == "__main__":
    main()
