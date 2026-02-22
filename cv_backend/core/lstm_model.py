import torch
import torch.nn as nn


class LSTMAutoencoder(nn.Module):
    """
    LSTM autoencoder for time-series anomaly detection.
    Trained on normal behaviour; high reconstruction error = anomaly.
    """

    def __init__(
        self,
        input_dim: int = 75,
        hidden_dim: int = 64,
        latent_dim: int = 32,
        num_layers: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim

        self.encoder_lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.encoder_fc = nn.Linear(hidden_dim, latent_dim)

        self.decoder_fc = nn.Linear(latent_dim, hidden_dim)
        self.decoder_lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.output_fc = nn.Linear(hidden_dim, input_dim)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.encoder_lstm(x)
        return self.encoder_fc(h_n[-1])

    def decode(self, latent: torch.Tensor, seq_len: int) -> torch.Tensor:
        h = self.decoder_fc(latent)
        h_repeated = h.unsqueeze(1).repeat(1, seq_len, 1)
        out, _ = self.decoder_lstm(h_repeated)
        return self.output_fc(out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encode(x)
        return self.decode(latent, x.size(1))
