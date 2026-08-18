"""Detección de anomalías sobre una serie temporal.

Método principal: z-score sobre media móvil. Para cada punto se compara su
valor con la media y desviación estándar de la ventana de días anteriores
(no incluye el propio punto, para que un pico no infle su propia línea
base). Si se desvía más de `threshold` desviaciones estándar, se marca como
anomalía.

Se incluye también IQR (rango intercuartílico) como método alternativo,
pensado para métricas con outliers naturales frecuentes donde el z-score
dispara demasiado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rolling_stats(values: pd.Series, window: int) -> tuple[pd.Series, pd.Series]:
    """Media y desviación estándar de la ventana previa a cada punto.

    Se desplaza un día (`shift(1)`) para que el propio valor evaluado nunca
    forme parte de su propia línea base.
    """
    previous = values.shift(1)
    mean = previous.rolling(window=window, min_periods=window).mean()
    std = previous.rolling(window=window, min_periods=window).std(ddof=0)
    return mean, std


def detect_zscore(
    df: pd.DataFrame, value_col: str, window: int, threshold: float,
) -> pd.DataFrame:
    out = df.copy()
    mean, std = _rolling_stats(out[value_col], window)
    out["expected_value"] = mean
    out["z_score"] = (out[value_col] - mean) / std.replace(0, np.nan)
    out["is_anomaly"] = out["z_score"].abs().ge(threshold).fillna(False)
    return out


def detect_iqr(
    df: pd.DataFrame, value_col: str, window: int, multiplier: float = 1.5,
) -> pd.DataFrame:
    out = df.copy()
    previous = out[value_col].shift(1)
    q1 = previous.rolling(window=window, min_periods=window).quantile(0.25)
    q3 = previous.rolling(window=window, min_periods=window).quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    out["expected_value"] = (q1 + q3) / 2
    out["lower_bound"] = lower
    out["upper_bound"] = upper
    out["is_anomaly"] = ((out[value_col] < lower) | (out[value_col] > upper)).fillna(False)
    return out


def detect_anomalies(
    df: pd.DataFrame,
    value_col: str = "value",
    window: int = 7,
    threshold: float = 2.0,
    method: str = "zscore",
    iqr_multiplier: float = 1.5,
) -> pd.DataFrame:
    """Punto de entrada único, seleccionable por `method` (config.yaml)."""
    if method == "zscore":
        return detect_zscore(df, value_col, window, threshold)
    if method == "iqr":
        return detect_iqr(df, value_col, window, iqr_multiplier)
    raise ValueError(f"Método de detección desconocido: {method!r} (usa 'zscore' o 'iqr')")
