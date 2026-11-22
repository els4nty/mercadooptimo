"""Modelo LSTM (PyTorch) para el precio del siguiente periodo.

Comparado con ARIMA en Menculini et al. [2]. Para cada serie (producto, tienda):

* se trabaja con los retornos logarítmicos r_t = log p_t - log p_{t-1}, que son
  aproximadamente estacionarios aunque el precio tenga tendencia inflacionaria;
* se estandarizan con la media y desviación del entrenamiento;
* la red recibe una ventana de `window` retornos y predice el siguiente;
* el pronóstico a h pasos es recursivo y se convierte de vuelta a precio;
* para no sobreajustar (las series semanales son cortas), el último 15 % de las
  ventanas de entrenamiento se usa como validación y se conservan los pesos de
  la época con menor error de validación (early stopping). El periodo de
  prueba nunca interviene en el entrenamiento.

Si la serie es demasiado corta para entrenar, se usa el modelo ingenuo.
PyTorch es una dependencia opcional: `pip install -e ".[lstm]"`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mercadooptimo.forecasting.models import Forecaster, NaiveForecaster


class LSTMForecaster(Forecaster):
    name = "lstm"

    def __init__(self, window: int = 12, hidden: int = 16, epochs: int = 200, lr: float = 0.01,
                 seed: int = 0, min_train: int = 30, val_frac: float = 0.15, weight_decay: float = 1e-4):
        self.window = window
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.seed = seed
        self.min_train = min_train
        self.val_frac = val_frac
        self.weight_decay = weight_decay
        self._net = None
        self._fallback: NaiveForecaster | None = None

    def _set_state(self, series: pd.Series) -> None:
        y = np.log(series.dropna().to_numpy(dtype=float))
        self._last_log = y[-1]
        self._recent = (np.diff(y)[-self.window:] - self._mu) / self._sd

    def fit(self, series: pd.Series) -> "LSTMForecaster":
        import torch
        from torch import nn

        values = series.dropna().to_numpy(dtype=float)
        if len(values) < self.window + self.min_train:
            self._fallback = NaiveForecaster().fit(series)
            return self
        self._fallback = None
        r = np.diff(np.log(values))
        self._mu, self._sd = float(r.mean()), float(r.std() or 1.0)
        z = (r - self._mu) / self._sd
        X = np.stack([z[k:k + self.window] for k in range(len(z) - self.window)])
        Y = z[self.window:]

        torch.manual_seed(self.seed)
        net = _Net(self.hidden)
        opt = torch.optim.Adam(net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        loss_fn = nn.MSELoss()
        xt = torch.tensor(X, dtype=torch.float32).unsqueeze(-1)
        yt = torch.tensor(Y, dtype=torch.float32)
        n_val = max(1, int(round(len(X) * self.val_frac)))
        x_tr, y_tr, x_va, y_va = xt[:-n_val], yt[:-n_val], xt[-n_val:], yt[-n_val:]
        best_loss, best_state = float("inf"), None
        for _ in range(self.epochs):
            net.train()
            opt.zero_grad()
            loss_fn(net(x_tr), y_tr).backward()
            opt.step()
            net.eval()
            with torch.no_grad():
                val = float(loss_fn(net(x_va), y_va))
            if val < best_loss:
                best_loss, best_state = val, {k: v.clone() for k, v in net.state_dict().items()}
        net.load_state_dict(best_state)
        net.eval()
        self._net = net
        self._set_state(series)
        return self

    def update(self, series: pd.Series) -> "LSTMForecaster":
        """Incorpora observaciones nuevas sin reentrenar la red."""
        if self._fallback is not None:
            self._fallback.fit(series)
        else:
            self._set_state(series)
        return self

    def predict(self, horizon: int = 1) -> np.ndarray:
        if self._fallback is not None:
            return self._fallback.predict(horizon)
        import torch

        window = list(self._recent)
        log_p, out = self._last_log, []
        with torch.no_grad():
            for _ in range(horizon):
                x = torch.tensor(window[-self.window:], dtype=torch.float32).view(1, -1, 1)
                z_next = float(self._net(x)[0])
                window.append(z_next)
                log_p += z_next * self._sd + self._mu
                out.append(np.exp(log_p))
        return np.array(out)


def _Net(hidden: int):
    from torch import nn

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    return Net()
