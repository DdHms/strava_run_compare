# from stravaio import strava_oauth2

import numpy as np
from stravaio import StravaIO

from run_compare.activity_analysis_utils import calculate_analysis, gather_data_for_plotting
from run_compare.constants import APP_CLIENT_ID, APP_CLIENT_SECRET
from run_compare.strava_api_utils import strava_oauth2, get_activities
from run_compare.visualisation_utils import plot_to_date

OFFLINE = False
DEBUG = False
INVALIDATE_HISTORY = False

if not OFFLINE:
    STRAVA_ACCESS_TOKEN = strava_oauth2(client_id=APP_CLIENT_ID,
                                        client_secret=APP_CLIENT_SECRET,
                                        port=8001)
    print('Connection succeeded')

    client = StravaIO(access_token=STRAVA_ACCESS_TOKEN['access_token'])
    athlete = client.get_logged_in_athlete()


    non_summarized, full_run_activities = get_activities(access_token=STRAVA_ACCESS_TOKEN['access_token'],
                                                         invalidate_history=INVALIDATE_HISTORY)
    for activity in non_summarized:
        calculate_analysis(athlete.id, activity['id'], client, debug=DEBUG)
    base_activities, interval_activities = gather_data_for_plotting(activity_list=full_run_activities)

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
f = plot_to_date(dates, speed, dspeed, color='rgba(0,200,255,', name='Speed [min/km]', label=label_base)

f = plot_to_date(idates, ispeed, idspeed, add_to_fig=f, color='rgba(150,200,255,', name='Speed [min/km]',
                 label=label_int)

f.show()  # f = plot_to_date(dates, hr, dhr, fig=f, name='Heart rate [BPM]', color='rgba(255,50,0,')
print('Done')
