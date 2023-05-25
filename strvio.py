# from stravaio import strava_oauth2
from datetime import datetime

import numpy as np
from stravaio import StravaIO

from activity_analysis_utils import activity_summarize
from constants import INTERVAL, BASE
from strava_api_utils import upload_description_from_summary, get_non_summarized_activities, get_run_activities, \
    get_full_activities, get_athlete_activities, strava_oauth2, exists_and_summarized, summary_from_description
from visualisation_utils import plot_to_date

OFFLINE = False
DEBUG = False
INVALIDATE_HISTORY = False

if not OFFLINE:
    STRAVA_ACCESS_TOKEN = strava_oauth2(client_id='94807',
                                        client_secret='6a9c293a602a6acefb1d7a2feb3d92242495dcf5',
                                        port=8001)
    print('Connection succeeded')

    client = StravaIO(access_token=STRAVA_ACCESS_TOKEN['access_token'])
    athlete = client.get_logged_in_athlete()

    list_of_activities = get_athlete_activities(access_token=STRAVA_ACCESS_TOKEN['access_token'], n=50)
    run_activities = get_run_activities(list_of_activities)
    full_run_activities = get_full_activities(STRAVA_ACCESS_TOKEN['access_token'], run_activities)
    non_summarized = full_run_activities if INVALIDATE_HISTORY else get_non_summarized_activities(full_run_activities)

    for activity in non_summarized:
        print(activity['id'])
        if not DEBUG:
            try:
                stream = client.get_activity_streams(activity['id'], athlete.id)
            except Exception as e:
                print(f'{activity["id"]} encountered exception {e}')
        else:
            print(f'loading activity {8704660889}')
            stream = next(client.local_streams(athlete_id=athlete.id))
        x = stream.distance
        y = stream.velocity_smooth
        if len(x) > 0 and len(y) > 0:
            summary = activity_summarize(stream)
            print(summary)
            upload_description_from_summary(summary, activity_id=activity['id'], client=client)

    base_activities = []
    interval_activities = []
    for activity in full_run_activities:
        if exists_and_summarized(activity):
            data = summary_from_description(activity['description'])
            date_entry = activity['start_date_local']
            date = datetime.fromisoformat(date_entry.split('T')[0] + ' ' + date_entry.split('T')[1].split('Z')[0])
            if data['type'] == BASE:
                data['data']['id'] = activity['id']
                data['data']['date'] = date
                base_activities.append(data['data'])
            elif data['type'] == INTERVAL:
                data['data']['id'] = activity['id']
                data['data']['date'] = date
                interval_activities.append(data['data'])

print('start')
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

label_base = [f'<a href="https://www.strava.com/activities/{base_activities[i]["id"]}"> {np.around(distance[i] / 1000, decimals=1)}k </a>' for i in range(len(distance))]
label_int = [f'<a href="https://www.strava.com/activities/{interval_activities[i]["id"]}"> {n_int[i]}X{np.int(100 * np.round(idistance[i] / 100))}m </a>' for i in range(len(idistance))]
f = plot_to_date(dates, speed, dspeed, name='Speed [min/km]', color='rgba(0,200,255,', label=label_base)

f = plot_to_date(idates, ispeed, idspeed, name='Speed [min/km]', color='rgba(150,200,255,', fig=f, label=label_int)

f.show()  # f = plot_to_date(dates, hr, dhr, fig=f, name='Heart rate [BPM]', color='rgba(255,50,0,')
print('Done')
