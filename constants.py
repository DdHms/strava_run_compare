import numpy as np

DESCRIPTION_HEADER = '#<-ACTIVITY SUMMARY START->#\n'
DESCRIPTION_FOOTER = '\n#<-ACTIVITY SUMMARY END->#'
DECIMALS = 3
BASE_BLOCK_TEMPLATE = 'base:{summary["data"]["DISTANCE"]}m@{summary["data"]["SPEED"]}\u00B1\u0394{summary["data"]["DSPEED"]}min/km\U0001fac0{summary["data"]["HR"]}\u00B1\u0394{summary["data"]["DHR"]}BPM'
INTERVAL_BLOCK_TEMPLATE = 'interval:{summary["data"]["N_INTERVALS"]}X[{summary["data"]["INTERVAL_DISTANCE"]}m@{summary["data"]["INTERVAL_SPEED"]}\u00B1\u0394{summary["data"]["DSPEED"]}min/km\U0001fac0{summary["data"]["INTERVAL_HR"]}]\u00B1\u0394{summary["data"]["DHR"]}BPM'
INTERVAL = 'interval'
BASE = 'base'


def wrap_interval_data(n_intervals, interval_distance, interval_speeds, d_speeds, intervals_hr, d_hr):
    return {'type': INTERVAL,
            'data': {'N_INTERVALS': np.int(n_intervals),
                     'INTERVAL_DISTANCE': np.float(interval_distance),
                     'INTERVAL_SPEED': np.float(interval_speeds),
                     'INTERVAL_HR': np.float(intervals_hr),
                     'DSPEED': np.around(np.float(d_speeds), decimals=DECIMALS),
                     'DHR': np.around(np.float(d_hr), decimals=0)}}


def wrap_base_data(distance, speed, d_speeds, hr, d_hr):
    return {'type': BASE,
            'data': {'SPEED': np.around(np.float(speed), decimals=DECIMALS),
                     'DISTANCE': np.around(np.float(distance), decimals=DECIMALS),
                     'HR': np.around(np.float(hr), decimals=DECIMALS),
                     'DSPEED': np.around(np.float(d_speeds), decimals=DECIMALS),
                     'DHR': np.around(np.float(d_hr), decimals=0)}}

