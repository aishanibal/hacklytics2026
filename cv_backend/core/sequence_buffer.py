from collections import deque

import numpy as np


class SequenceBuffer:
    """Sliding-window buffer that collects keypoint feature vectors for the LSTM."""

    def __init__(self, window_size: int = 9, num_features: int = 75, stride: int = 1):
        self.window_size = window_size
        self.num_features = num_features
        self.stride = stride
        self._buffer: deque[np.ndarray] = deque(maxlen=window_size)
        self._since_last = 0

    def add(self, features: np.ndarray) -> bool:
        """
        Append one feature vector.
        Returns True when a full window is ready for inference.
        """
        self._buffer.append(features)
        self._since_last += 1
        if len(self._buffer) == self.window_size and self._since_last >= self.stride:
            self._since_last = 0
            return True
        return False

    def get_window(self) -> np.ndarray:
        """Return current window as (window_size, num_features) array."""
        return np.array(list(self._buffer), dtype=np.float32)

    def reset(self):
        self._buffer.clear()
        self._since_last = 0
