from run_compare.activity_analysis_utils import load_stream, activity_summarize, is_periodic
from skimage.restoration import denoise_tv_chambolle
import numpy as np
import ruptures as rpt
from run_compare.activity_analysis_utils import find_intervals, extract_base_data, extract_interval_data


# from sklearn.mixture import GaussianMixture


activity_id = '18274877830'
stream = load_stream(activity_id)
summary = activity_summarize(stream)
velocity = np.asarray(stream.velocity_smooth)
cadence = np.asarray(stream.cadence)

# Apply TVD to get the piecewise signal
clean_signal = denoise_tv_chambolle(velocity[:, np.newaxis], weight=500)
clean_cadence = denoise_tv_chambolle(cadence[:, np.newaxis], weight=500)

model = rpt.Pelt(model="rbf").fit(clean_cadence)
result = model.predict(pen=10)  # 'pen' controls sensitivity to noise

# 2. Reconstruct the signal from segment means
piecewise_signal = np.zeros_like(clean_signal)
for start, end in zip([0] + result[:-1], result):
    piecewise_signal[start:end] = np.mean(clean_signal[start:end])


if is_periodic(piecewise_signal):
    alternations = find_intervals(piecewise_signal[:, 0])
    summary = extract_interval_data(alternations, stream.distance, stream.speed_smoothed, stream.heartrate,
                                    stream.speed_smoothed)
else:
    summary = extract_base_data(stream.speed_smoothed, stream.distance, stream.heartrate)

#
#
# gmm = GaussianMixture(n_components=5).fit(segment_means)
# labels = gmm.predict(segment_means)
#
# # Identify jumps (derivative thresholding)
# diffs = np.diff(clean_signal)
# jump_indices = np.where(np.abs(diffs) > stream.velocity_smooth)[0] + 1
