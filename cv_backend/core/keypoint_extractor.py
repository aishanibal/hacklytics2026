import cv2
import numpy as np
from ultralytics import YOLO

# COCO skeleton limbs for manual drawing
_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),        # head
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # arms
    (5, 11), (6, 12), (11, 12),              # torso
    (11, 13), (13, 15), (12, 14), (14, 16),  # legs
]


class KeypointExtractor:
    """YOLOv8-pose: detect persons, draw skeletons, return keypoints + bboxes."""

    def __init__(self, model_name: str = "yolov8n-pose.pt"):
        self.model = YOLO(model_name)

    def extract(self, frame: np.ndarray) -> tuple[np.ndarray | None, np.ndarray]:
        """Single-person shortcut: returns first person's (17,3) keypoints."""
        results = self.model(frame, verbose=False)
        annotated = results[0].plot()
        if results[0].keypoints is not None and len(results[0].keypoints.data) > 0:
            return results[0].keypoints.data[0].cpu().numpy(), annotated
        return None, annotated

    def extract_all(self, frame: np.ndarray) -> list[dict]:
        """
        Returns list of detections, one per person:
          [{"bbox": [x1,y1,x2,y2], "keypoints": (17,3) ndarray, "conf": float}, ...]
        """
        results = self.model(frame, verbose=False)
        r = results[0]
        detections: list[dict] = []
        if r.boxes is not None and r.keypoints is not None:
            boxes = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            all_kps = r.keypoints.data.cpu().numpy()
            for i in range(len(boxes)):
                detections.append({
                    "bbox": boxes[i].tolist(),
                    "keypoints": all_kps[i],
                    "conf": float(confs[i]),
                })
        return detections

    @staticmethod
    def draw_skeleton(frame: np.ndarray, kps: np.ndarray,
                      color: tuple = (0, 255, 0), thickness: int = 2,
                      label: str | None = None,
                      bbox: list | None = None) -> np.ndarray:
        """Draw skeleton + optional bbox + label for one person."""
        out = frame
        h, w = out.shape[:2]

        if bbox is not None:
            x1, y1, x2, y2 = (int(v) for v in bbox)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness)
            if label:
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(out, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                cv2.putText(out, label, (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

        for i, (x, y, c) in enumerate(kps):
            if c > 0.3:
                cv2.circle(out, (int(x), int(y)), 4, color, -1)

        for j1, j2 in _SKELETON:
            if kps[j1][2] > 0.3 and kps[j2][2] > 0.3:
                pt1 = (int(kps[j1][0]), int(kps[j1][1]))
                pt2 = (int(kps[j2][0]), int(kps[j2][1]))
                cv2.line(out, pt1, pt2, color, thickness)

        return out

    def close(self):
        pass
