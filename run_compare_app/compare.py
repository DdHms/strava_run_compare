import threading

import numpy as np
import requests

from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
# from run_compare.main import access_token
from run_compare.visualisation_utils import plot_to_date
from run_compare_app import app
from run_compare.stravaio import StravaIO, run_server_and_wait_for_token, run_server_and_wait_for_token_
from run_compare.strava_api_utils import get_strava_oauth2_url, get_activities, get_strava_token_from_url
from flask import render_template, request, redirect, session, render_template_string, jsonify

from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET, BASE_COLOR, INTERVAL_COLOR
from plotly.utils import PlotlyJSONEncoder
import json

global_session = {}
session_ready = threading.Event()  # Synchronization object


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

    listener_thread = threading.Thread(
        target=run_server_and_wait_for_token_,
        args=(APP_CLIENT_ID, APP_CLIENT_SECRET),
        kwargs={'session': global_session, 'event': session_ready},
        daemon=False
    )
    listener_thread.start()
    # Redirect the user to the Strava OAuth URL
    environment_template = render_template('index.html', refreshed=False)
    redirect_template = render_template('welcome.html', externalUrl=oauth_url)
    environment_template = environment_template.replace('<!-- graph -->', redirect_template)
    return redirect(f'/redirect_to_strava?url={oauth_url}')

@app.route('/redirect_to_strava')
def redirect_to_strava():
    """
    Generates a small HTML page to open the Strava OAuth URL in a new tab
    and close itself once authentication is completed.
    """
    strava_oauth_url = request.args.get('url')  # Get the URL from query parameters
    if not strava_oauth_url:
        return "Error: No URL provided", 400

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Redirecting...</title>
        <script>
            // Open the OAuth URL in a new tab
            const oauthWindow = window.open("{strava_oauth_url}", "_blank");
            // Close the current tab/window after a short delay
            setTimeout(() => window.close(), 1000);
        </script>
    </head>
    <body>
        <p>Redirecting to Strava for authentication...</p>
    </body>
    </html>
    """
    return html
@app.route('/status')
def status():
    """Checks if the access token has been received."""
    if access_token:
        return jsonify({"status": "success", "access_token": access_token})
    else:
        return jsonify({"status": "pending", "message": "Waiting for authentication..."})

@app.route('/authorization_successful')#, methods=['GET'])
def authorization_successful():
    # Extract the authorization code from the query parameters
    print('authorization_successful')
    authorization_code = request.args.get('code')
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
    return redirect('/activities')

    # STRAVA_ACCESS_TOKEN = get_strava_token_from_url(
    #     url=oauth_url,
    #     client_id=APP_CLIENT_ID,
    #     client_secret=APP_CLIENT_SECRET,
    #     port=8001
    # )
    #
    # client = StravaIO(access_token=STRAVA_ACCESS_TOKEN['access_token'])
    # athlete = client.get_logged_in_athlete()
    # athlete_dict = athlete.to_dict()
    # session['athlete_name'] = athlete_dict['firstname'] + ' ' + athlete_dict['lastname']
    # session['access_token'] = STRAVA_ACCESS_TOKEN['access_token']
    # session['athlete_id'] = athlete.id
    # # session['client'] = client
    # # segment_ids_from_activities(client, max_activities = 5) # sets segment_ids_unique
    # return redirect('/activities')
    # if you want a simple output of first name, last name, just use this line:
    # return athlete.firstname + ' ' + athlete.lastname

@app.route('/activities')
def options():
    client = StravaIO(access_token=session['access_token'])
    non_summarized, full_run_activities = get_activities(access_token=session['access_token'], invalidate_history=False)
    for activity in non_summarized:
        calculate_analysis(athlete_id=session['athlete_id'], activity_id=activity['id'], client=client)
    base_activities, interval_activities = gather_data_for_plotting(activity_list=full_run_activities)
    session['base_activities'] = base_activities
    session['interval_activities'] = interval_activities
    return redirect('/graph')


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
    return environment_template


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

    lnk = lambda i: f'https://www.strava.com/activities/{base_activities[i]["id"]}'
    dis = lambda i: np.around(distance[i] / 1000, decimals=1)
    sp = lambda i: f'{int(np.floor(speed[i]))}:{int(np.round(60 * np.remainder(speed[i], 1))):02}'
    label_base = [
        f'<a href="{lnk(i)}"> {dis(i)}k <br> @{sp(i)} </a>' for i in range(len(distance))]
    lnk = lambda i: f'https://www.strava.com/activities/{interval_activities[i]["id"]}'
    dis = lambda i: int(100 * np.around(idistance[i] / 1000, decimals=1))
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
