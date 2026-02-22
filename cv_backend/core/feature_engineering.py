"""
Transform raw YOLO (17, 3) keypoints into the 75-feature vector
that matches the Colab-trained LSTM autoencoder.

  34  raw normalized (x, y) for 17 joints
  34  delta (x, y) velocity from previous frame
   7  engineered: nose_y, hip_y, torso_len, full_height,
                  shoulder_angle, knee_angle, vertical_ratio
  --
  75  total
"""

import numpy as np

# COCO-17 indices
_NOSE = 0
_L_SHOULDER, _R_SHOULDER = 5, 6
_L_ELBOW, _R_ELBOW = 7, 8
_L_HIP, _R_HIP = 11, 12
_L_KNEE, _R_KNEE = 13, 14
_L_ANKLE, _R_ANKLE = 15, 16


def _joint_angle(a: np.ndarray, vertex: np.ndarray, c: np.ndarray) -> float:
    v1 = a - vertex
    v2 = c - vertex
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    return float(np.arccos(np.clip(cos_a, -1.0, 1.0)))


class FeatureEngineer:
    """Stateful: keeps previous frame's xy for velocity computation."""

    def __init__(self):
        self._prev_xy: np.ndarray | None = None

    def compute(self, kps: np.ndarray, frame_w: int, frame_h: int) -> np.ndarray:
        """
        kps: (17, 3) raw YOLO keypoints (pixel x, pixel y, confidence).
        Returns: (75,) feature vector.
        """
        xy = kps[:, :2].copy().astype(np.float32)
        xy[:, 0] /= frame_w
        xy[:, 1] /= frame_h

        # --- 34 raw normalised x,y ---
        raw_xy = xy.flatten()

        # --- 34 delta x,y (velocity) ---
        if self._prev_xy is not None:
            delta_xy = (xy - self._prev_xy).flatten()
        else:
            delta_xy = np.zeros(34, dtype=np.float32)
        self._prev_xy = xy.copy()

        # --- 7 engineered features ---
        nose = xy[_NOSE]
        l_sh, r_sh = xy[_L_SHOULDER], xy[_R_SHOULDER]
        l_el, r_el = xy[_L_ELBOW], xy[_R_ELBOW]
        l_hp, r_hp = xy[_L_HIP], xy[_R_HIP]
        l_kn, r_kn = xy[_L_KNEE], xy[_R_KNEE]
        l_ak, r_ak = xy[_L_ANKLE], xy[_R_ANKLE]

        shoulder_mid = (l_sh + r_sh) / 2
        hip_mid = (l_hp + r_hp) / 2
        ankle_mid = (l_ak + r_ak) / 2

        nose_y = nose[1]
        hip_y = hip_mid[1]
        torso_len = float(np.linalg.norm(shoulder_mid - hip_mid))
        full_height = float(np.linalg.norm(nose - ankle_mid))

        shoulder_angle = (
            _joint_angle(l_el, l_sh, l_hp) +
            _joint_angle(r_el, r_sh, r_hp)
        ) / 2

        knee_angle = (
            _joint_angle(l_hp, l_kn, l_ak) +
            _joint_angle(r_hp, r_kn, r_ak)
        ) / 2

        vertical_ratio = torso_len / (full_height + 1e-8)

        engineered = np.array([
            nose_y, hip_y, torso_len, full_height,
            shoulder_angle, knee_angle, vertical_ratio,
        ], dtype=np.float32)

        return np.concatenate([raw_xy, delta_xy, engineered])

    def reset(self):
        self._prev_xy = None
