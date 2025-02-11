import streamlit as st
import pandas as pd
import numpy as np
import requests
import threading
from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
from run_compare.prompt_constants import SUGGESTED_EXERCISE_PROMPT, SYSTEM_PROMPT, ai_schema_type_json
from run_compare.visualisation_utils import plot_to_date, speed_to_pace, distance_display
from run_compare.stravaio import StravaIO
from run_compare.strava_api_utils import get_strava_oauth2_url, get_activities
from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET, BASE_COLOR, INTERVAL_COLOR, N_ACTIVITIES
from plotly.utils import PlotlyJSONEncoder
import json

# Global session management
global_session = {}
session_ready = threading.Event()

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

def collect_data_for_fig(base_activities, interval_activities):
    distance = [data['DISTANCE'] for data in base_activities]
    hr = [data['HR'] for data in base_activities]
    dspeed = [data['DSPEED'] for data in base_activities]
    dhr = [data['DHR'] for data in base_activities]
    speed = [data['SPEED'] for data in base_activities]
    dates = [data['date'] for data in base_activities]
    marker_col = [BASE_COLOR] * len(distance)

    idistance = [data['INTERVAL_DISTANCE'] for data in interval_activities]
    n_int = [data['N_INTERVALS'] for data in interval_activities]
    ihr = [data['INTERVAL_HR'] for data in interval_activities]
    idspeed = [data['DSPEED'] for data in interval_activities]
    idhr = [data['DHR'] for data in interval_activities]
    ispeed = [data['INTERVAL_SPEED'] for data in interval_activities]
    idates = [data['date'] for data in interval_activities]
    imarker_col = [INTERVAL_COLOR] * len(idistance)

    ord = np.argsort(dates + idates)
    all_dates = sorted(dates + idates)
    all_speeds = np.array(speed + ispeed)[ord].tolist()
    all_dspeeds = np.array(dspeed + idspeed)[ord].tolist()
    all_hr = np.array(hr + ihr)[ord].tolist()
    all_dhr = np.array(dhr + idhr)[ord].tolist()
    all_marker_col = np.array(marker_col + imarker_col)[ord].tolist()
    return {'all_dates': all_dates,
            'all_speeds': all_speeds,
            'all_dspeeds': all_dspeeds,
            'all_hr': all_hr,
            'all_dhr': all_dhr,
            'all_marker_col': all_marker_col}

def main():
    st.title("Run Compare App")

    if 'code' not in global_session:
        oauth_url = get_strava_oauth2_url(client_id=APP_CLIENT_ID, client_secret=APP_CLIENT_SECRET, port=8001)
        st.markdown(f"[Authorize with Strava]({oauth_url})")
    else:
        authorization_code = global_session['code']
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": APP_CLIENT_ID,
                "client_secret": APP_CLIENT_SECRET,
                "code": authorization_code,
                "grant_type": "authorization_code"
            }
        )
        response_data = response.json()
        STRAVA_ACCESS_TOKEN = response_data['access_token']
        client = StravaIO(access_token=STRAVA_ACCESS_TOKEN)
        athlete = client.get_logged_in_athlete()
        athlete_dict = athlete.to_dict()
        st.sidebar.write(f"Logged in as {athlete_dict['firstname']} {athlete_dict['lastname']}")

        non_summarized, full_run_activities = get_activities(access_token=STRAVA_ACCESS_TOKEN,
                                                             invalidate_history=False,
                                                             num_activities=N_ACTIVITIES)
        for activity in non_summarized:
            calculate_analysis(athlete_id=athlete.id, activity_id=activity['id'], client=client)

        base_activities, interval_activities = gather_data_for_plotting(activity_list=full_run_activities)

        st.sidebar.write("## Activity Data")
        if st.sidebar.button("Show Graph"):
            fig_data = collect_data_for_fig(base_activities, interval_activities)

            fig = plot_to_date(fig_data['all_dates'], fig_data['all_speeds'], fig_data['all_dspeeds'], color='rgba(0,100,255,',
                               name='Speed [min/km]', marker_col=fig_data['all_marker_col'])
            fig = plot_to_date(fig_data['all_dates'], fig_data['all_hr'], fig_data['all_dhr'], color='rgba(255,100,0,',
                               name='HR [BPM]', add_to_fig=fig, separate=True)

            st.plotly_chart(fig)

        if st.sidebar.button("Show Activities Table"):
            df = convert_activities_to_df(base_activities, interval_activities)
            st.dataframe(df)

        if st.sidebar.button("Ask AI"):
            df = convert_activities_to_df(base_activities, interval_activities)
            data = df.to_dict(orient='index')
            request = {'user_prompt': SUGGESTED_EXERCISE_PROMPT,
                       'system_prompt': SYSTEM_PROMPT,
                       'schema': ai_schema_type_json,
                       'context': data}

            response = requests.post('http://localhost:3888/generate', json=request)
            st.write(response.json())

if __name__ == "__main__":
    main()
