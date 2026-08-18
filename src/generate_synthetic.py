"""Genera una serie temporal sintética para probar el detector de anomalías.

La serie combina tendencia + estacionalidad semanal + ruido, y fuerza unas
pocas anomalías (picos y caídas) en posiciones conocidas para poder
comprobar que `anomaly.py` las detecta sin tocar ningún dato real.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_DAYS = 90
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "synthetic_metric.csv"

# (día relativo al inicio de la serie, tipo, magnitud como fracción de la
# línea base). Los offsets dejan siempre >=7 días de contexto por delante y
# por detrás para que la ventana móvil del detector esté completa.
FORCED_ANOMALIES = [
    (20, "spike", 2.5),   # pico brusco
    (40, "drop", -0.6),   # caída fuerte
    (60, "spike", 1.8),
    (75, "drop", -0.8),
]


def generate_series(days: int = DEFAULT_DAYS, seed: int = 42) -> pd.DataFrame:
    """Crea `days` días de una métrica ficticia (p.ej. "instalaciones")."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq="D")

    baseline = 500.0
    trend = np.linspace(0, 80, days)  # crecimiento suave a lo largo del periodo

    # Más actividad entre semana, caída moderada el fin de semana. La
    # amplitud se mantiene contenida a propósito: con una ventana de 7 días
    # y z-score sin desestacionalizar, un patrón semanal demasiado marcado
    # se confunde con una anomalía real (los domingos "normales" disparan
    # el detector). Con esta amplitud el ruido normal se queda por debajo
    # del umbral y solo saltan las anomalías forzadas.
    weekday = dates.dayofweek.to_numpy()  # 0=lunes ... 6=domingo
    weekly_factor = np.array([1.00, 1.02, 1.02, 1.04, 1.06, 0.92, 0.88])
    seasonality = weekly_factor[weekday] * baseline - baseline

    noise = rng.normal(0, 18, size=days)

    values = baseline + trend + seasonality + noise

    forced_mask = np.zeros(days, dtype=bool)
    for offset, _kind, magnitude in FORCED_ANOMALIES:
        if offset >= days:
            continue
        values[offset] += baseline * magnitude
        forced_mask[offset] = True

    values = np.clip(values, a_min=0, a_max=None)

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "value": np.round(values, 2),
        "is_forced_anomaly": forced_mask,
    })


def save(df: pd.DataFrame, output: Path = DEFAULT_OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return output


def plot(df: pd.DataFrame, output: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(pd.to_datetime(df["date"]), df["value"], label="valor", color="#2563eb")
    forced = df[df["is_forced_anomaly"]]
    ax.scatter(
        pd.to_datetime(forced["date"]), forced["value"],
        color="#dc2626", zorder=5, label="anomalía forzada",
    )
    ax.set_title("Serie sintética con anomalías forzadas")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Valor")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--plot", action="store_true", help="Guarda también un PNG con la serie")
    args = parser.parse_args()

    df = generate_series(days=args.days, seed=args.seed)
    path = save(df, args.output)
    print(f"Datos sintéticos guardados en {path} ({len(df)} filas)")

    forced_dates = df.loc[df["is_forced_anomaly"], "date"].tolist()
    print(f"Anomalías forzadas en: {', '.join(forced_dates)}")

    if args.plot:
        plot_path = path.parent / "synthetic_metric.png"
        plot(df, plot_path)
        print(f"Gráfico guardado en {plot_path}")


if __name__ == "__main__":
    main()
