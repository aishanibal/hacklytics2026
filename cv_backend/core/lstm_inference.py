import os
from pathlib import Path

import numpy as np
import torch

from .lstm_model import LSTMAutoencoder


class AnomalyPredictor:
    """Load the Colab-trained LSTM autoencoder and run anomaly detection on keypoint windows."""

    def __init__(self, model_path: str = "models/pots_model_complete.pt", device: str | None = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)

        checkpoint = torch.load(
            Path(model_path), map_location=self.device, weights_only=False
        )

        self.model_config: dict = checkpoint["model_config"]
        self.pipeline_config: dict = checkpoint["pipeline_config"]

        self.model = LSTMAutoencoder(**self.model_config)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.to(self.device)
        self.model.eval()

        self.mean: torch.Tensor = checkpoint["mean"].to(self.device)
        self.std: torch.Tensor = checkpoint["std"].to(self.device)
        default_threshold: float = checkpoint["anomaly_threshold"].item()
        override = os.getenv("ANOMALY_THRESHOLD", "").strip()
        self.threshold: float = float(override) if override else default_threshold

        self.window_size: int = self.pipeline_config["window_size"]
        self.num_features: int = self.pipeline_config["num_features"]

    def _normalize(self, features: np.ndarray) -> torch.Tensor:
        t = torch.tensor(features, dtype=torch.float32, device=self.device)
        return (t - self.mean) / (self.std + 1e-8)

    @torch.no_grad()
    def predict(self, window: np.ndarray) -> dict:
        """
        window: (window_size, num_features) numpy array
        Returns {"score": float, "is_anomaly": bool, "threshold": float}
        """
        x = self._normalize(window).unsqueeze(0)  # (1, T, F)
        reconstructed = self.model(x)
        mse = torch.mean((x - reconstructed) ** 2).item()
        return {
            "score": mse,
            "is_anomaly": mse > self.threshold,
            "threshold": self.threshold,
        }
