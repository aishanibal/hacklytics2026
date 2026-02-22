"""
Heuristic anomaly classifier.

When the LSTM autoencoder flags an anomaly, this inspects the
feature window to classify it into one of 4 types:
  FAINTING, SWAYING, CROUCHING, HAND ON HEAD, or UNKNOWN.
"""

import numpy as np

COLOR_MAP = {
    'FAINTING':     (0, 0, 255),      # red
    'SWAYING':      (0, 165, 255),     # orange
    'CROUCHING':    (255, 100, 0),     # blue
    'HAND ON HEAD': (0, 255, 0),       # green
    'UNKNOWN':      (128, 128, 128),   # gray
}


def classify_anomaly(window: np.ndarray) -> tuple[str, tuple[int, int, int]]:
    """
    Classify anomalous window into 4 types.
    window shape: (WINDOW_SIZE, 75)

    Feature index reference:
      0-33:  raw normalized joint positions (x,y for 17 joints)
      34-67: deltas (velocity)
      68: nose_y, 69: hip_y, 70: torso_len, 71: full_height
      72: shoulder_angle, 73: knee_angle, 74: vertical_ratio
    """

    nose_y     = window[:, 68]
    hip_y      = window[:, 69]
    torso_len  = window[:, 70]
    sh_angle   = window[:, 72]
    knee_ang   = window[:, 73]
    vert_ratio = window[:, 74]

    delta_nose_y = window[:, 35]

    l_wrist_y = window[:, 19]
    r_wrist_y = window[:, 21]

    signatures = {
        'FAINTING': {
            'checks': {
                'nose_drop':       (nose_y[-1] - nose_y[0]) > 0.1,
                'fast_drop':       np.max(np.abs(delta_nose_y)) > 0.03,
                'went_horizontal': vert_ratio[-1] > vert_ratio[0] * 1.5,
                'knee_buckle':     knee_ang[-1] < knee_ang[0] - 0.3,
            },
            'priority': 4,
        },
        'SWAYING': {
            'checks': {
                'nose_oscillation': np.std(nose_y) > 0.015,
                'hip_oscillation':  np.std(hip_y) > 0.01,
                'still_upright':    abs(nose_y[-1] - nose_y[0]) < 0.08,
                'shoulder_wobble':  np.std(sh_angle) > 0.05,
            },
            'priority': 3,
        },
        'CROUCHING': {
            'checks': {
                'knees_bent':       knee_ang[-1] < knee_ang[0] - 0.2,
                'hip_lowered':      (hip_y[-1] - hip_y[0]) > 0.05,
                'torso_compressed': torso_len[-1] < torso_len[0] * 0.8,
                'still_vertical':   vert_ratio[-1] < 1.0,
            },
            'priority': 2,
        },
        'HAND ON HEAD': {
            'checks': {
                'wrist_above_nose': (np.any(l_wrist_y < nose_y + 0.05) or
                                     np.any(r_wrist_y < nose_y + 0.05)),
                'shoulder_asym':    np.max(np.abs(sh_angle)) > 0.15,
                'no_drop':          abs(nose_y[-1] - nose_y[0]) < 0.05,
                'still_upright':    vert_ratio[-1] < 0.8,
            },
            'priority': 1,
        },
    }

    matches = {}
    for label, sig in signatures.items():
        score = sum(sig['checks'].values()) / len(sig['checks'])
        if score >= 0.5:
            matches[label] = (score, sig['priority'])

    if not matches:
        return 'UNKNOWN', COLOR_MAP['UNKNOWN']

    best = max(matches, key=lambda k: (matches[k][1], matches[k][0]))
    return best, COLOR_MAP[best]
