from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parents[1]))

from run_compare.activity_analysis_utils import (
    convert_mps_mpkm,
    extract_base_data,
    is_periodic,
    load_stream,
    smooth_signal,
)
from run_compare.constants import DECIMALS, wrap_interval_data


@dataclass
class Segment:
    kind: str
    start: int
    end: int


@dataclass
class Rep:
    start: int
    end: int
    distance: float
    duration: float
    pace: float
    hr: float


def bool_runs(mask):
    """Return contiguous (value, start, end) runs for a boolean mask."""
    if len(mask) == 0:
        return []

    starts = np.r_[0, np.flatnonzero(mask[1:] != mask[:-1]) + 1]
    ends = np.r_[starts[1:], len(mask)]
    return [(bool(mask[start]), int(start), int(end)) for start, end in zip(starts, ends)]


def close_short_gaps(mask, max_gap=20):
    cleaned = mask.copy()
    for value, start, end in bool_runs(mask):
        if not value and end - start <= max_gap:
            cleaned[start:end] = True
    return cleaned


def remove_short_efforts(mask, min_effort=20):
    cleaned = mask.copy()
    for value, start, end in bool_runs(mask):
        if value and end - start < min_effort:
            cleaned[start:end] = False
    return cleaned


def merge_ranges(ranges):
    if not ranges:
        return []

    merged = [list(ranges[0])]
    for start, end in ranges[1:]:
        last = merged[-1]
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return [(int(start), int(end)) for start, end in merged]


def detect_local_periodic_regions(speed_smoothed, window_width=600, step=100, min_region_width=200, padding=150):
    speed_smoothed = np.asarray(speed_smoothed)
    regions = []

    for start in range(0, max(len(speed_smoothed) - window_width + 1, 1), step):
        end = min(start + window_width, len(speed_smoothed))
        if end - start < min_region_width:
            continue

        try:
            periodic = is_periodic(speed_smoothed[start:end])
        except (FloatingPointError, ValueError, IndexError):
            periodic = False

        if periodic:
            regions.append((start, end))

    regions = merge_ranges(regions)
    padded_regions = [
        (max(0, start - padding), min(len(speed_smoothed), end + padding))
        for start, end in regions
    ]
    return merge_ranges(padded_regions)


def detect_fast_segments(speed_smoothed, periodic_regions=None, min_effort=20, max_gap=20):
    speed_smoothed = np.asarray(speed_smoothed)
    regions = periodic_regions or [(0, len(speed_smoothed))]
    is_fast = np.zeros(len(speed_smoothed), dtype=bool)

    for start, end in regions:
        region_speed = speed_smoothed[start:end]
        if len(region_speed) == 0:
            continue

        low = np.percentile(region_speed, 35)
        high = np.percentile(region_speed, 75)
        threshold = low + 0.55 * (high - low)
        is_fast[start:end] |= region_speed > threshold

    is_fast = close_short_gaps(is_fast, max_gap=max_gap)
    is_fast = remove_short_efforts(is_fast, min_effort=min_effort)

    segments = []
    for value, start, end in bool_runs(is_fast):
        segments.append(Segment("fast" if value else "base", start, end))
    return segments


def summarize_reps(segments, time, distance, speed, hr):
    time = np.asarray(time)
    distance = np.asarray(distance)
    speed = np.asarray(speed)
    hr = np.asarray(hr) if hr is not None else None

    reps = []
    for segment in segments:
        if segment.kind != "fast":
            continue

        start = segment.start
        end = segment.end - 1
        if end <= start:
            continue

        rep_speed = speed[start:end]
        rep_hr = hr[start:end] if hr is not None else np.asarray([np.nan])
        reps.append(
            Rep(
                start=start,
                end=end,
                distance=float(distance[end] - distance[start]),
                duration=float(time[end] - time[start]),
                pace=float(np.median(convert_mps_mpkm(rep_speed))),
                hr=float(np.nanmedian(rep_hr)),
            )
        )
    return reps


def is_similar_rep(rep, block, distance_abs_tol=100, distance_rel_tol=0.25, duration_rel_tol=0.30):
    block_distances = np.asarray([item.distance for item in block])
    block_durations = np.asarray([item.duration for item in block])

    distance_ref = np.median(block_distances)
    duration_ref = np.median(block_durations)
    distance_tol = max(distance_abs_tol, distance_rel_tol * distance_ref)
    duration_tol = duration_rel_tol * duration_ref

    same_distance = abs(rep.distance - distance_ref) <= distance_tol
    same_duration = abs(rep.duration - duration_ref) <= duration_tol
    return same_distance or same_duration


def group_reps_into_sets(reps, min_reps=2):
    if not reps:
        return []

    sets = []
    current = [reps[0]]

    for rep in reps[1:]:
        if is_similar_rep(rep, current):
            current.append(rep)
        else:
            if len(current) >= min_reps:
                sets.append(current)
            current = [rep]

    if len(current) >= min_reps:
        sets.append(current)

    return sets


def summarize_rep_set(rep_set):
    distances = np.asarray([rep.distance for rep in rep_set])
    paces = np.asarray([rep.pace for rep in rep_set])
    hrs = np.asarray([rep.hr for rep in rep_set])

    return wrap_interval_data(
        n_intervals=len(rep_set),
        interval_distance=np.around(np.median(distances), decimals=DECIMALS),
        interval_speeds=np.around(np.mean(paces), decimals=DECIMALS),
        d_speeds=np.around(np.std(paces), decimals=DECIMALS),
        intervals_hr=np.around(np.nanmean(hrs), decimals=DECIMALS),
        d_hr=np.around(np.nanstd(hrs), decimals=0),
    )


def build_blocks(rep_sets, activity_end):
    blocks = []
    cursor = 0

    for rep_set in rep_sets:
        set_start = rep_set[0].start
        set_end = rep_set[-1].end

        if cursor < set_start:
            blocks.append({"type": "base", "start": cursor, "end": set_start})

        blocks.append(
            {
                "type": "interval_set",
                "start": set_start,
                "end": set_end,
                "reps": rep_set,
                "summary": summarize_rep_set(rep_set),
            }
        )
        cursor = set_end

    if cursor < activity_end:
        blocks.append({"type": "base", "start": cursor, "end": activity_end})

    for i, block in enumerate(blocks):
        if block["type"] != "base":
            continue

        if i == 0:
            block["label"] = "warmup"
        elif i == len(blocks) - 1:
            block["label"] = "cooldown"
        else:
            block["label"] = "transition"

    return blocks


def summarize_activity_blocks(stream, kernel_width=50):
    time = getattr(stream, "time", np.arange(len(stream.distance)))
    distance = np.asarray(stream.distance)
    speed = np.asarray(stream.velocity_smooth)
    hr = getattr(stream, "heartrate", None)
    speed_smoothed = smooth_signal(speed, kernel_width=kernel_width)

    periodic_regions = detect_local_periodic_regions(speed_smoothed)
    segments = detect_fast_segments(speed_smoothed, periodic_regions=periodic_regions)
    reps = summarize_reps(segments, time, distance, speed, hr)
    rep_sets = group_reps_into_sets(reps)
    blocks = build_blocks(rep_sets, activity_end=len(distance) - 1)

    if not rep_sets:
        return {
            "type": "base",
            "segments": segments,
            "periodic_regions": periodic_regions,
            "reps": reps,
            "sets": [],
            "blocks": [{"type": "base", "label": "base", "start": 0, "end": len(distance) - 1}],
            "summary": extract_base_data(speed_smoothed, distance, hr),
        }

    return {
        "type": "workout",
        "segments": segments,
        "periodic_regions": periodic_regions,
        "reps": reps,
        "sets": rep_sets,
        "blocks": blocks,
        "summary": [summarize_rep_set(rep_set) for rep_set in rep_sets],
    }


def print_workout(result):
    print(f"activity type: {result['type']}")

    print("\nperiodic regions:")
    if result["periodic_regions"]:
        for i, (start, end) in enumerate(result["periodic_regions"], start=1):
            print(f"{i:02d}: idx {start:>4}-{end:<4}")
    else:
        print("none")

    print("\nblocks:")
    for i, block in enumerate(result["blocks"], start=1):
        if block["type"] == "base":
            label = block.get("label", "base")
            print(f"{i:02d}: {label:<12} idx {block['start']:>4}-{block['end']:<4}")
        else:
            rep_set = block["reps"]
            distances = [rep.distance for rep in rep_set]
            paces = [rep.pace for rep in rep_set]
            print(
                f"{i:02d}: interval_set idx {block['start']:>4}-{block['end']:<4} "
                f"{len(rep_set)}x{np.median(distances):.0f}m "
                f"@ {np.mean(paces):.2f}min/km"
            )

    print("\nfast reps:")
    for i, rep in enumerate(result["reps"], start=1):
        print(
            f"{i:02d}: idx {rep.start:>4}-{rep.end:<4} "
            f"{rep.distance:>6.1f}m {rep.duration:>5.0f}s "
            f"{rep.pace:>5.2f}min/km HR {rep.hr:>5.1f}"
        )

    print("\nsets:")
    for i, rep_set in enumerate(result["sets"], start=1):
        distances = [rep.distance for rep in rep_set]
        paces = [rep.pace for rep in rep_set]
        print(
            f"set {i}: {len(rep_set)}x"
            f"{np.median(distances):.0f}m "
            f"@ {np.mean(paces):.2f}min/km"
        )

    print("\nsummary:")
    print(result["summary"])


if __name__ == "__main__":
    activity_id = "18180793871"
    stream = load_stream(activity_id)
    result = summarize_activity_blocks(stream)
    print_workout(result)
