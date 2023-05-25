import matplotlib.pyplot as plt
import numpy as np

from constants import wrap_interval_data, wrap_base_data, DECIMALS


def conv_sad(f, k):
    sad = []
    for i in range(len(f) - len(k)):
        f_ = f[i:i + len(k)]
        sad.append(np.sum(np.abs((k - f_))))
    return np.asarray(sad)


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
    return wrap_base_data(convert_mps_mpkm(np.mean(speed)), np.std(speed), np.max(distance), np.mean(hr), np.std(hr))


def find_periodicity(signal, basic_period, abs=False):
    from scipy.signal import find_peaks
    signal_ = signal - signal.mean()
    conv = np.convolve(signal_, basic_period, mode='same')
    conv = conv / conv.max()
    if abs:
        conv = np.abs(conv)
    p, _ = find_peaks(conv, height=0.6, width=20)
    return p


def is_periodic(signal):
    accelerations = find_alternations(signal)
    if accelerations.shape[0] >= 2:
        return True
    else:
        return False


def find_alternations(signal, window_width=100, with_accelerations=False):
    sign_function = np.sign(np.arange(window_width) - window_width / 2)
    periods = find_periodicity(signal, sign_function, abs=with_accelerations)
    return periods


def find_intervals(signal):
    decelerations = find_alternations(signal)
    alternations = find_alternations(signal, with_accelerations=True)
    accelerations = np.sort(list(set(alternations) - set(decelerations)))
    first_positive_alternation = np.where(alternations == accelerations[0])[0]
    alternations = alternations[int(first_positive_alternation):]
    n_intervals = 2 * (len(alternations) // 2)
    alternations = np.reshape(alternations[:n_intervals], [n_intervals // 2, 2])
    return alternations

def extract_interval_data(alternations, distance, speed, hr):
    distance = np.asarray(distance)
    speed = np.asarray(speed)
    hr = np.asarray(hr)
    start_idxs = alternations[:, 0].tolist()
    end_idxs = alternations[:, 1].tolist()
    distances = np.asarray(distance)[end_idxs] - np.asarray(distance)[start_idxs]
    groups = np.where(np.abs(np.diff(distances)) < 100)[0]
    if len(groups) < 1:
        print('activity was wrongly thought to be interval')
        return wrap_base_data(np.max(distance), convert_mps_mpkm(np.mean(speed)), np.mean(hr), np.std(speed), np.std(hr))
    main_group = (groups[0], groups[-1] + 2)
    start_idxs = start_idxs[main_group[0]:main_group[1]]
    end_idxs = end_idxs[main_group[0]:main_group[1]]
    distances = distances[main_group[0]:main_group[1]]
    alternations = alternations[main_group[0]:main_group[1], :]
    all_idxs = np.asarray([np.arange(strt, end).tolist() for strt, end in alternations])
    int_speeds = np.asarray([speed[int_idxs] for int_idxs in all_idxs])
    int_hr = np.asarray([hr[int_idxs] for int_idxs in all_idxs])
    n_intervals = alternations.shape[0]
    med_dist = np.around(np.mean(distances), decimals=DECIMALS)
    med_int_speed = np.around(np.mean([np.median(int_speed) for int_speed in int_speeds]), decimals=DECIMALS)
    med_int_hr = np.around(np.mean([np.median(hrs) for hrs in int_hr]), decimals=DECIMALS)
    d_hr = np.around(np.std([np.median(hrs) for hrs in int_hr]), decimals=0)
    d_speeds = np.around(np.std([np.median(int_speed) for int_speed in int_speeds]), decimals=DECIMALS)

    return wrap_interval_data(n_intervals, med_dist, convert_mps_mpkm(med_int_speed), d_speeds, med_int_hr, d_hr)


def activity_summarize(stream, kernel_width=100):
    distance = stream.distance
    speed = stream.velocity_smooth
    hr = stream.heartrate
    kernel = np.array([0] * kernel_width)
    kernel[5:-5] = 1
    kernel = kernel / np.sum(kernel)
    speed_smoothed = np.convolve(speed, kernel, 'same')
    if is_periodic(speed_smoothed):
        alternations = find_intervals(speed_smoothed)
        summary = extract_interval_data(alternations, distance, speed, hr)
    else:
        summary = extract_base_data(speed_smoothed, distance, hr)
    return summary
