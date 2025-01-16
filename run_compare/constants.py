import numpy as np

DESCRIPTION_HEADER = '#<-ACTIVITY SUMMARY START->#\n'
DESCRIPTION_FOOTER = '\n#<-ACTIVITY SUMMARY END->#'
DECIMALS = 3
BASE_BLOCK_TEMPLATE = 'base:{summary["data"]["DISTANCE"]}m@{summary["data"]["SPEED"]}\u00B1\u0394{summary["data"]["DSPEED"]}min/km\U0001fac0{summary["data"]["HR"]}\u00B1\u0394{summary["data"]["DHR"]}BPM'
INTERVAL_BLOCK_TEMPLATE = 'interval:{summary["data"]["N_INTERVALS"]}X[{summary["data"]["INTERVAL_DISTANCE"]}m@{summary["data"]["INTERVAL_SPEED"]}\u00B1\u0394{summary["data"]["DSPEED"]}min/km\U0001fac0{summary["data"]["INTERVAL_HR"]}]\u00B1\u0394{summary["data"]["DHR"]}BPM'
INTERVAL = 'interval'
BASE = 'base'
N_ACTIVITIES = 20
APP_CLIENT_ID = '94807'
APP_CLIENT_SECRET = '6a9c293a602a6acefb1d7a2feb3d92242495dcf5'
BASE_COLOR = 'rgba(0,100,255,1)'
INTERVAL_COLOR = 'rgba(0,200,200,1)'

def wrap_interval_data(n_intervals, interval_distance, interval_speeds, d_speeds, intervals_hr, d_hr):
    return {'type': INTERVAL,
            'data': {'N_INTERVALS': int(n_intervals),
                     'INTERVAL_DISTANCE': np.float64(interval_distance),
                     'INTERVAL_SPEED': np.float64(interval_speeds),
                     'INTERVAL_HR': np.float64(intervals_hr),
                     'DSPEED': np.around(np.float64(d_speeds), decimals=DECIMALS),
                     'DHR': np.around(np.float64(d_hr), decimals=0)}}


def wrap_base_data(distance, speed, d_speeds, hr, d_hr):
    return {'type': BASE,
            'data': {'SPEED': np.around(np.float64(speed), decimals=DECIMALS),
                     'DISTANCE': np.around(np.float64(distance), decimals=DECIMALS),
                     'HR': np.around(np.float64(hr), decimals=DECIMALS),
                     'DSPEED': np.around(np.float64(d_speeds), decimals=DECIMALS),
                     'DHR': np.around(np.float64(d_hr), decimals=0)}}

