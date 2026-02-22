"""
Heuristic anomaly classifier.

When the LSTM autoencoder flags an anomaly, this inspects the
feature window to classify it into one of 4 types:
  FAINTING, SWAYING, CROUCHING, HAND ON HEAD, or UNKNOWN.

FAINTING is safety-critical and always takes precedence.
"""

import numpy as np

COLOR_MAP = {
    'FAINTING':     (0, 0, 255),      # red
    'SWAYING':      (0, 165, 255),     # orange
    'CROUCHING':    (255, 100, 0),     # blue
    'HAND ON HEAD': (0, 255, 0),       # green
    'UNKNOWN':      (128, 128, 128),   # gray
}

# Per-type minimum score to qualify as a match.
# FAINTING is deliberately low so it fires on weak evidence;
# HAND ON HEAD is high to suppress noise-driven false positives.
_MIN_SCORE = {
    'FAINTING':     0.35,
    'SWAYING':      0.50,
    'CROUCHING':    0.50,
    'HAND ON HEAD': 0.75,
}


def _fraction_true(arr: np.ndarray) -> float:
    """Fraction of frames where a boolean condition is True."""
    return float(np.mean(arr))


def classify_anomaly(window: np.ndarray) -> tuple[str, tuple[int, int, int]]:
    """
    Classify anomalous window into 4 types.
    window shape: (WINDOW_SIZE, 75)

    Feature index reference (from FeatureEngineer):
      0-33:  raw normalized joint positions (x,y for 17 joints)
             joint i  →  x = 2*i, y = 2*i+1
      34-67: deltas (velocity)
             joint i  →  dx = 34+2*i, dy = 34+2*i+1
      68: nose_y, 69: hip_y, 70: torso_len, 71: full_height
      72: shoulder_angle, 73: knee_angle, 74: vertical_ratio
    """

    nose_y     = window[:, 68]
    hip_y      = window[:, 69]
    torso_len  = window[:, 70]
    full_height = window[:, 71]
    sh_angle   = window[:, 72]
    knee_ang   = window[:, 73]
    vert_ratio = window[:, 74]

    delta_nose_y = window[:, 35]       # nose dy per frame

    # Wrist positions (COCO: 9=L_WRIST, 10=R_WRIST)
    l_wrist_x = window[:, 18]
    l_wrist_y = window[:, 19]
    r_wrist_x = window[:, 20]
    r_wrist_y = window[:, 21]

    # Nose x for spatial proximity check
    nose_x = window[:, 0]

    # ── FAINTING ───────────────────────────────────────────────
    # Relaxed: any 2 of 5 signals is enough (35% threshold).
    # nose_drop threshold lowered; added hip_drop as extra signal.
    faint_checks = {
        'nose_drop':       (nose_y[-1] - nose_y[0]) > 0.06,
        'fast_drop':       np.max(np.abs(delta_nose_y)) > 0.02,
        'went_horizontal': vert_ratio[-1] > vert_ratio[0] * 1.3,
        'knee_buckle':     knee_ang[-1] < knee_ang[0] - 0.2,
        'hip_drop':        (hip_y[-1] - hip_y[0]) > 0.05,
    }

    # ── SWAYING ────────────────────────────────────────────────
    sway_checks = {
        'nose_oscillation': np.std(nose_y) > 0.015,
        'hip_oscillation':  np.std(hip_y) > 0.01,
        'still_upright':    abs(nose_y[-1] - nose_y[0]) < 0.08,
        'shoulder_wobble':  np.std(sh_angle) > 0.05,
    }

    # ── CROUCHING ──────────────────────────────────────────────
    crouch_checks = {
        'knees_bent':       knee_ang[-1] < knee_ang[0] - 0.2,
        'hip_lowered':      (hip_y[-1] - hip_y[0]) > 0.05,
        'torso_compressed': torso_len[-1] < torso_len[0] * 0.8,
        'still_vertical':   vert_ratio[-1] < 1.0,
    }

    # ── HAND ON HEAD ───────────────────────────────────────────
    # Much stricter: require wrist *well above* nose for a majority
    # of frames AND wrist spatially close to the head in x.
    wrist_above_margin = -0.03   # wrist must be at least 3% of frame above nose
    l_above = l_wrist_y < (nose_y + wrist_above_margin)
    r_above = r_wrist_y < (nose_y + wrist_above_margin)

    l_near_head_x = np.abs(l_wrist_x - nose_x) < 0.12
    r_near_head_x = np.abs(r_wrist_x - nose_x) < 0.12

    l_on_head = l_above & l_near_head_x
    r_on_head = r_above & r_near_head_x

    # Require >=40% of frames showing hand on head, not just any single frame
    hand_sustained = (_fraction_true(l_on_head) > 0.4 or
                      _fraction_true(r_on_head) > 0.4)

    hoh_checks = {
        'wrist_on_head':    hand_sustained,
        'shoulder_raised':  np.mean(sh_angle) > 0.3,
        'no_drop':          abs(nose_y[-1] - nose_y[0]) < 0.04,
        'still_upright':    np.mean(vert_ratio) < 0.6,
    }

    signatures = {
        'FAINTING':     {'checks': faint_checks,  'priority': 10},
        'SWAYING':      {'checks': sway_checks,   'priority': 3},
        'CROUCHING':    {'checks': crouch_checks,  'priority': 2},
        'HAND ON HEAD': {'checks': hoh_checks,     'priority': 1},
    }

    matches = {}
    for label, sig in signatures.items():
        score = sum(sig['checks'].values()) / len(sig['checks'])
        if score >= _MIN_SCORE[label]:
            matches[label] = (score, sig['priority'])

    if not matches:
        return 'UNKNOWN', COLOR_MAP['UNKNOWN']

    # FAINTING always wins when it matches, regardless of other scores
    if 'FAINTING' in matches:
        return 'FAINTING', COLOR_MAP['FAINTING']

    best = max(matches, key=lambda k: (matches[k][1], matches[k][0]))
    return best, COLOR_MAP[best]
