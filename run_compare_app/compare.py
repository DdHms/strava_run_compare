import threading

import numpy as np
import pandas as pd
import requests

from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
from run_compare.prompt_constants import SUGGESTED_EXERCISE_PROMPT, SYSTEM_PROMPT, ai_schema_type_json
from run_compare.visualisation_utils import plot_to_date, speed_to_pace, distance_display
from run_compare_app import app
from run_compare.stravaio import StravaIO, run_server_and_wait_for_token, run_server_and_wait_for_token_
from run_compare.strava_api_utils import get_strava_oauth2_url, get_activities, get_strava_token_from_url
from flask import render_template, request, redirect, session, render_template_string, jsonify, url_for, make_response

from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET, BASE_COLOR, INTERVAL_COLOR, N_ACTIVITIES
from plotly.utils import PlotlyJSONEncoder
import json

global_session = {}
session_ready = threading.Event()  # Synchronization object

def convert_activities_to_df(base_activities, inteval_activities):
    # Convert lists to DataFrames
    base_df = pd.DataFrame(base_activities)
    intervals_df = pd.DataFrame(inteval_activities)

    # Add a source column to each DataFrame
    base_df['source'] = 'base_activity'
    intervals_df['source'] = 'interval'

    # Rename columns for clarity
    base_df.rename(columns={'SPEED': 'BASE_SPEED', 'DISTANCE': 'BASE_DISTANCE', 'HR': 'BASE_HR'}, inplace=True)
    intervals_df.rename(columns={'INTERVAL_SPEED': 'INTERVAL_SPEED', 'INTERVAL_DISTANCE': 'INTERVAL_DISTANCE',
                                 'INTERVAL_HR': 'INTERVAL_HR'}, inplace=True)

    # Combine DataFrames and sort by date
    combined_df = pd.concat([base_df, intervals_df], ignore_index=True).sort_values(by='date').reset_index(drop=True)

    # Helper functions to format columns
    def format_distance(row):
        if row['source'] == 'base_activity':
            return distance_display(row['BASE_DISTANCE'])
        elif row['source'] == 'interval':
            return f"{int(row['N_INTERVALS'])} X {distance_display(row['INTERVAL_DISTANCE'])}"

    def format_hr(row):
        return int(row['BASE_HR']) if row['source'] == 'base_activity' else int(row['INTERVAL_HR'])

    def format_speed(row):
        return speed_to_pace(row['BASE_SPEED']) if row['source'] == 'base_activity' else speed_to_pace(row['INTERVAL_SPEED'])

    # Create the formatted DataFrame
    formatted_df = pd.DataFrame({
        'date': combined_df['date'].apply(lambda x: x.strftime("%d/%m/%Y")),
        'source': combined_df['source'],
        'distance': combined_df.apply(format_distance, axis=1),
        'HR': combined_df.apply(format_hr, axis=1),
        'pace': combined_df.apply(format_speed, axis=1),  # TODO: display pace hms
    })

    return formatted_df

@app.route('/')
@app.route('/index', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')
    else:
        return redirect('/login')


@app.route('/login')
def main():
    oauth_url = get_strava_oauth2_url(client_id=APP_CLIENT_ID, client_secret=APP_CLIENT_SECRET, port=8001)
    # Here I want an html page to open the oauth_url in a new tab and close itself
    print(oauth_url)
    return render_template('welcome.html', url=oauth_url)

@app.route('/authorization_successful')#, methods=['GET'])
def authorization_successful():
    # Extract the authorization code from the query parameters
    print('authorization_successful')
    authorization_code = request.args.get('code')
    global_session['code'] = authorization_code
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
    session['athlete_name'] = athlete_dict['firstname'] + ' ' + athlete_dict['lastname']
    session['access_token'] = STRAVA_ACCESS_TOKEN
    session['athlete_id'] = athlete.id
    # session['client'] = client
    # segment_ids_from_activities(client, max_activities = 5) # sets segment_ids_unique
    client = StravaIO(access_token=session['access_token'])
    non_summarized, full_run_activities = get_activities(access_token=session['access_token'], invalidate_history=False,
                                                         num_activities=N_ACTIVITIES)
    for activity in non_summarized:
        calculate_analysis(athlete_id=session['athlete_id'], activity_id=activity['id'], client=client)
    base_activities, interval_activities = gather_data_for_plotting(activity_list=full_run_activities)
    session['base_activities'] = base_activities
    session['interval_activities'] = interval_activities
    return  redirect('/graph')


@app.route('/graph')
def page1():
    fig_data = collect_data_for_fig(base_activities=session['base_activities'],
                                    interval_activities=session['interval_activities'])

    fig = plot_to_date(fig_data['all_dates'], fig_data['all_speeds'], fig_data['all_dspeeds'], color='rgba(0,100,255,',
                       name='Speed [min/km]', label=fig_data['all_labels'], marker_col=fig_data['all_marker_col'])
    fig = plot_to_date(fig_data['all_dates'], fig_data['all_hr'], fig_data['all_dhr'], color='rgba(255,100,0,',
                       name='HR [BPM]', label=[f'{int(hr)}\U0001fac0' for hr in fig_data['all_hr']], add_to_fig=fig, separate=True)

    # Convert the figure to JSON
    fig_json = json.dumps(fig, cls=PlotlyJSONEncoder)

    environment_template = render_template('index.html')
    graph_template = render_template('graph_page.html', graph_json=fig_json)
    environment_template = environment_template.replace('<!-- graph -->', graph_template)
    response = make_response(environment_template)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response

@app.route('/activities')
def activities():
    df = convert_activities_to_df(base_activities=session['base_activities'],
                                  inteval_activities=session['interval_activities'])

    # Convert DataFrame to HTML
    # html_table = df.to_html(classes='table table-striped')
    html_table = df.style.set_table_styles([
        # General table styles
        {'selector': 'table', 'props': [
            ('border-collapse', 'collapse'),
            ('width', '100%'),  # Ensure the table takes up the full width
            ('font-family', 'Arial, sans-serif'),  # Nicer font
            ('font-size', '14px'),  # Slightly larger font size
        ]},
        # Header styles
        {'selector': 'th', 'props': [
            ('background-color', '#f2f2f2'),  # Light grey background for header
            ('color', '#333'),  # Dark text color for contrast
            ('padding', '12px'),  # Add padding for more spacing
            ('text-align', 'left'),  # Left-align text
            ('border', '1px solid #ddd'),  # Border around header cells
        ]},
        # Data cell styles
        {'selector': 'td', 'props': [
            ('background-color', 'rgba(255, 255, 255, 0.8)'),  # Semi-transparent white
            ('padding', '12px'),  # Add padding for more spacing
            ('border', '1px solid #ddd'),  # Border around data cells
            ('text-align', 'left'),  # Left-align text
        ]},
        # Row hover effect
        {'selector': 'tr:hover', 'props': [
            ('background-color', '#f1f1f1'),  # Light grey background on hover
        ]}
    ]).set_properties(**{
        # Setting a min-width for all columns
        'width': '150px',  # Wider columns for better readability
    }).to_html()
    # Pass the HTML table to the template
    environment_template = render_template('index.html')
    table_template = render_template('table.html', table=html_table)
    environment_template = environment_template.replace('<!-- graph -->', table_template)
    response = make_response(environment_template)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response

@app.route('/ai')
def ask_ai():
    df = convert_activities_to_df(base_activities=session['base_activities'],
                                  inteval_activities=session['interval_activities'])
    data = df.to_dict(orient='index')
    request = {'user_prompt': SUGGESTED_EXERCISE_PROMPT,
               'system_prompt': SYSTEM_PROMPT,  #still problem here TODO fix
               'schema': ai_schema_type_json,
               'context': data}

    #post the request to the AI server at localhost port 3888
    response = requests.post('http://localhost:3888/generate', json=request)
    try:
        print(eval(eval(response.text)['response']))
    except:
        pass
    return response.json()


def collect_data_for_fig(base_activities, interval_activities):
    distance = [data['DISTANCE'] for data in base_activities]
    hr = [data['HR'] for data in base_activities]
    dspeed = [data['DSPEED'] for data in base_activities]
    dhr = [data['DHR'] for data in base_activities]
    speed = [data['SPEED'] for data in base_activities]  # TODO: fix pace display hms
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

    lnk = lambda i: f'https://www.strava.com/activities/{base_activities[i]["id"]}'
    dis = lambda i: np.around(distance[i] / 1000, decimals=1)   # TODO: fix distance display
    sp = lambda i: speed_to_pace(speed[i])
    label_base = [
        f'<a href="{lnk(i)}"> {dis(i)}k <br> @{sp(i)} </a>' for i in range(len(distance))]
    lnk = lambda i: f'https://www.strava.com/activities/{interval_activities[i]["id"]}'
    dis = lambda i: int(100 * np.around(idistance[i] / 100, decimals=1))  # TODO: fix distance display
    sp = lambda i: f'{int(np.floor(ispeed[i]))}:{int(np.round(60 * np.remainder(ispeed[i], 1))):02}'
    label_int = [
        f'<a href="{lnk(i)}"> {n_int[i]}X{dis(i)}m  <br> @{sp(i)} </a>' for i in range(len(idistance))]

    ord = np.argsort(dates + idates)
    all_dates = sorted(dates + idates)
    all_speeds = np.array(speed + ispeed)[ord].tolist()
    all_dspeeds = np.array(dspeed + idspeed)[ord].tolist()
    all_hr = np.array(hr + ihr)[ord].tolist()
    all_dhr = np.array(dhr + idhr)[ord].tolist()
    all_labels = np.array(label_base + label_int)[ord].tolist()
    all_marker_col = np.array(marker_col + imarker_col)[ord].tolist()
    return {'all_dates': all_dates,
            'all_speeds': all_speeds,
            'all_dspeeds': all_dspeeds,
            'all_hr': all_hr,
            'all_dhr': all_dhr,
            'all_labels': all_labels,
            'all_marker_col': all_marker_col}

@app.route('/result')
def result():
    pass
