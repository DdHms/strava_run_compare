import json
import subprocess
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import ruptures as rpt
from scipy.fft import fft, fftshift

from run_compare.constants import BASE, INTERVAL
from run_compare.constants import wrap_interval_data, wrap_base_data, DECIMALS
from run_compare.strava_api_utils import upload_description_from_summary, exists_and_summarized, \
    summary_from_description
# from run_compare.strvio import activity


def conv_sad(f, k):
    sad = []
    for i in range(len(f) - len(k)):
        f_ = f[i:i + len(k)]
        sad.append(np.sum(np.abs((k - f_))))
    return np.asarray(sad)


def segment_activity_with_ruptures(speed_smoothed, model="rbf", pen=10):
    algo = rpt.Pelt(model=model).fit(speed_smoothed)
    change_points = algo.predict(pen=pen)

    # Output format: list of (start_idx, end_idx)
    start_idx = 0
    segments = []
    for end_idx in change_points:
        segments.append((start_idx, end_idx))
        start_idx = end_idx
    return segments


def debug_intervals(distance, speed_smoothed, matching, det, high_matches, first_sprint_abs_idxs, last_sprint_abs_idxs,
                    first_sprint_dis, last_sprint_dis):
    plt.scatter(high_matches, high_matches * 0 + 1, c='g');
    plt.scatter(first_sprint_abs_idxs, first_sprint_abs_idxs * 0 + 1, c='r');
    plt.scatter(last_sprint_abs_idxs, last_sprint_abs_idxs * 0 + 1, c='b');
    plt.plot(matching, c='k');
    plt.grid(True)
    plt.show()

    plt.scatter(first_sprint_dis, first_sprint_dis * 0 + 1, c='r');
    plt.scatter(det, det * 0 + 1, c='g');
    plt.scatter(last_sprint_dis, last_sprint_dis * 0 + 1, c='b');
    plt.plot(distance, speed_smoothed, c='k');
    plt.grid(True)
    plt.show()


def convert_mps_mpkm(speed, epsilon=0.001):
    return 1 / (epsilon + speed * 3.6 / 60)


def extract_base_data(speed, distance, hr):
    return wrap_base_data(speed=np.mean(convert_mps_mpkm(speed)), d_speeds=np.std(convert_mps_mpkm(speed)),
                          distance=np.max(distance), hr=np.mean(hr), d_hr=np.std(hr))

def spectral_analysis(pace_data, fs):
  """
  Analyzes the frequency content of pace data.
  Args:
    pace_data: 1D numpy array containing pace values.
    fs: Sampling frequency (e.g., data points per second).
  Returns:
    frequencies: Array of frequencies corresponding to the FFT output.
    fft_abs: Absolute values of the Fast Fourier Transform.
  """
  # Calculate FFT
  fft_data = fft(pace_data)
  fft_abs = np.abs(fftshift(fft_data)) / len(pace_data)  # Normalize magnitude
  # Calculate corresponding frequencies
  frequencies = np.linspace(0, fs / 2, len(fft_abs))
  return frequencies, fft_abs


def find_periodicity(signal, basic_period, abs=False, fft=True):
    from scipy.signal import find_peaks
    signal_ = signal - signal.mean()
    signal_ = np.clip(signal_, 0, None)
    conv = np.convolve(signal_, basic_period, mode='same')
    conv = conv / conv.max()
    if abs:
        conv = np.abs(conv)
    if fft:
        frequencies, fft_abs = spectral_analysis(conv, fs=1)
        p = find_peaks(fft_abs, height=0.075)[0]
    else:
        p, _ = find_peaks(conv, height=0.5, width=20)
    return p


def is_periodic(signal):
    accelerations = find_alternations(signal)
    if accelerations.shape[0] >= 2:
        return True
    else:
        return False


def find_alternations(signal, window_width=100, with_accelerations=False, fft=True):
    sign_function = np.sign(np.arange(window_width) - window_width / 2)
    periods = find_periodicity(signal, sign_function, abs=with_accelerations, fft=fft)
    return periods


def find_intervals(signal):
    decelerations = find_alternations(signal, fft=False)
    alternations = find_alternations(signal, with_accelerations=True, fft=False)
    accelerations = np.sort(list(set(alternations) - set(decelerations)))
    first_positive_alternation = np.where(alternations == accelerations[0])[0]
    alternations = alternations[int(first_positive_alternation):]
    n_intervals = 2 * (len(alternations) // 2)
    alternations = np.reshape(alternations[:n_intervals], [n_intervals // 2, 2])
    return alternations

def extract_interval_data(alternations, distance, speed, hr, speed_smoothed):
    distance = np.asarray(distance)
    speed = np.asarray(speed)
    hr = np.asarray(hr)
    start_idxs = alternations[:, 0].tolist()
    end_idxs = alternations[:, 1].tolist()
    distances = np.asarray(distance)[end_idxs] - np.asarray(distance)[start_idxs]
    groups = np.where(np.abs(np.diff(distances)) < 100)[0]
    if len(groups) < 1:
        print(f'activity was wrongly thought to be interval')
        return extract_base_data(speed_smoothed, distance, hr)

    main_group = (groups[0], groups[-1] + 2)
    start_idxs = start_idxs[main_group[0]:main_group[1]]
    end_idxs = end_idxs[main_group[0]:main_group[1]]
    distances = distances[main_group[0]:main_group[1]]
    alternations = alternations[main_group[0]:main_group[1], :]
    all_idxs = np.asarray(sum([np.arange(strt, end).tolist() for strt, end in alternations], []))
    int_speeds = np.asarray([speed[int_idxs] for int_idxs in all_idxs])
    int_hr = np.asarray([hr[int_idxs] for int_idxs in all_idxs])
    n_intervals = alternations.shape[0]
    med_dist = np.around(np.mean(distances), decimals=DECIMALS)
    med_int_speed = np.around(np.mean([np.median(convert_mps_mpkm(int_speed)) for int_speed in int_speeds]),
                              decimals=DECIMALS)
    med_int_hr = np.around(np.mean([np.median(hrs) for hrs in int_hr]), decimals=DECIMALS)
    d_hr = np.around(np.std([np.median(hrs) for hrs in int_hr]), decimals=0)
    d_speeds = np.around(np.std([np.median(convert_mps_mpkm(int_speed)) for int_speed in int_speeds]),
                         decimals=DECIMALS)
    # TODO: improve interval start-end times
    return wrap_interval_data(n_intervals, med_dist, med_int_speed, d_speeds, med_int_hr, d_hr)

def extract_multi_interval_data_with_ruptures(speed_smoothed, distance, speed, hr):
    distance = np.asarray(distance)
    speed = np.asarray(speed)
    hr = np.asarray(hr)

    segments = segment_activity_with_ruptures(speed_smoothed)

    interval_summaries = []

    for (start, end) in segments:
        seg_speed = speed_smoothed[start:end]
        if is_periodic(seg_speed):
            # Find alternations *within* this segment
            alternations = find_intervals(seg_speed)
            if len(alternations) >= 2:
                # Offset alternation indices to global indices
                alternations = alternations + start
                summary = extract_interval_data(alternations, distance, speed, hr, speed_smoothed)
                interval_summaries.append(summary)

    if not interval_summaries:
        print("No valid interval blocks found with ruptures, falling back to base effort")
        return extract_base_data(speed_smoothed, distance, hr)

    return interval_summaries


def activity_summarize(stream, kernel_width=50):
    distance = stream.distance
    speed = stream.velocity_smooth
    hr = stream.heartrate
    kernel = np.array([0] * kernel_width)
    kernel[5:-5] = 1
    kernel = kernel / np.sum(kernel)
    speed_smoothed = np.convolve(speed, kernel, 'same')
    if is_periodic(speed_smoothed):  # interval
        # alternations = find_intervals(speed_smoothed)
        summary = extract_multi_interval_data_with_ruptures(speed_smoothed, distance, speed, hr)
    else:  # Base
        summary = extract_base_data(speed_smoothed, distance, hr)
    return summary


def calculate_analysis(activity_id, access_token, debug=False):
    if not debug:
        print(f'loading activity {activity_id}')
        try:
            # stream = client.get_activity_streams(activity_id, athlete_id)
            keys = ['time', 'distance', 'latlng', 'altitude', 'velocity_smooth',
                    'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth']
            result = subprocess.run(f"curl --location --request GET 'https://www.strava.com/api/v3/activities/{activity_id}/streams?keys={','.join(keys)}&key_by_type=true&access_token={access_token}'",
                                    shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Error fetching activity streams: {result.stderr}")
            data = json.loads(result.stdout)
            data = {k: v.get('data') for k, v in data.items()}
            Stream = type('Stream', (object,), data)
            stream = Stream()

        except Exception as e:
            print(f'{activity_id} encountered exception {e}')
            if '429' in e:
                print('Rate limit exceeded try again in 15 minutes: https://www.strava.com/settings/api')
                exit(1)
    else:
        print(f'loading activity {8704660889}')
        print('Deprecated for now...')
        # stream = next(client.local_streams(athlete_id=athlete_id))

    x = stream.distance
    y = stream.velocity_smooth
    if x is None or y is None:
        print(f'activity {activity_id} has no distance or velocity')
        return
    if len(x) > 0 and len(y) > 0:
        summary = activity_summarize(stream)
        print(summary)
        upload_description_from_summary(summary, activity_id=activity_id, access_token=access_token)


def gather_data_for_plotting(activity_list):
    base_activities = []
    interval_activities = []
    for activity in activity_list:
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
    return base_activities, interval_activities