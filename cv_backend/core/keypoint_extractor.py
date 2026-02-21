import numpy as np
from ultralytics import YOLO


class KeypointExtractor:
    """YOLOv8-pose: detect person, draw skeleton, return raw keypoints."""

    def __init__(self, model_name: str = "yolov8n-pose.pt"):
        self.model = YOLO(model_name)

    def extract(self, frame: np.ndarray) -> tuple[np.ndarray | None, np.ndarray]:
        """
        Returns (kps_raw, annotated_frame).
        kps_raw: (17, 3) array [x, y, conf] in pixel coords, or None if no person.
        annotated_frame: frame with skeleton + boxes drawn by YOLO.
        """
        results = self.model(frame, verbose=False)
        annotated = results[0].plot()

        if results[0].keypoints is not None and len(results[0].keypoints.data) > 0:
            kps = results[0].keypoints.data[0].cpu().numpy()  # (17, 3)
            return kps, annotated

        return None, annotated

    def close(self):
        pass
