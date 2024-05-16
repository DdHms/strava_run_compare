import numpy as np

from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
from run_compare.visualisation_utils import plot_to_date
from run_compare_app import app
from stravaio import StravaIO
from run_compare.strava_api_utils import strava_oauth2, get_activities
from flask import render_template, request, redirect, session

from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET
from plotly.utils import PlotlyJSONEncoder
import json


@app.route('/')
@app.route('/index', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')
    else:
        return redirect('/login')


@app.route('/login')
def main():
    STRAVA_ACCESS_TOKEN = strava_oauth2(client_id=APP_CLIENT_ID, client_secret=APP_CLIENT_SECRET, port=8001)

    client = StravaIO(access_token=STRAVA_ACCESS_TOKEN['access_token'])
    athlete = client.get_logged_in_athlete()
    athlete_dict = athlete.to_dict()
    session['athlete_name'] = athlete_dict['firstname'] + ' ' + athlete_dict['lastname']
    session['access_token'] = STRAVA_ACCESS_TOKEN['access_token']
    session['athlete_id'] = athlete.id
    # session['client'] = client
    # segment_ids_from_activities(client, max_activities = 5) # sets segment_ids_unique
    return redirect('/activities')
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
                       name='Speed [min/km]', label=fig_data['all_labels'])
    fig = plot_to_date(fig_data['all_dates'], fig_data['all_hr'], fig_data['all_dhr'], color='rgba(255,100,0,',
                       name='HR [BPM]', label=fig_data['all_labels'], add_to_fig=fig, separate=True)

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

    idistance = [data['INTERVAL_DISTANCE'] for data in interval_activities]
    n_int = [data['N_INTERVALS'] for data in interval_activities]
    ihr = [data['INTERVAL_HR'] for data in interval_activities]
    idspeed = [data['DSPEED'] for data in interval_activities]
    idhr = [data['DHR'] for data in interval_activities]
    ispeed = [data['INTERVAL_SPEED'] for data in interval_activities]
    idates = [data['date'] for data in interval_activities]

    label_base = [
        f'<a href="https://www.strava.com/activities/{base_activities[i]["id"]}"> {np.around(distance[i] / 1000, decimals=1)}k <br> @{int(np.floor(speed[i]))}:{int(np.round(60 * np.remainder(speed[i], 1))):02} </a>'
        for i in range(len(distance))]
    label_int = [
        f'<a href="https://www.strava.com/activities/{interval_activities[i]["id"]}"> {n_int[i]}X{np.int(100 * np.round(idistance[i] / 100))}m  <br> @{int(np.floor(ispeed[i]))}:{int(np.round(60 * np.remainder(ispeed[i], 1))):02} </a>'
        for i in range(len(idistance))]

    ord = np.argsort(dates + idates)
    all_dates = sorted(dates + idates)
    all_speeds = np.array(speed + ispeed)[ord].tolist()
    all_dspeeds = np.array(dspeed + idspeed)[ord].tolist()
    all_hr = np.array(hr + ihr)[ord].tolist()
    all_dhr = np.array(dhr + idhr)[ord].tolist()
    all_labels = np.array(label_base + label_int)[ord].tolist()
    return {'all_dates': all_dates,
            'all_speeds': all_speeds,
            'all_dspeeds': all_dspeeds,
            'all_hr': all_hr,
            'all_dhr': all_dhr,
            'all_labels': all_labels}


@app.route('/result')
def result():
    pass
