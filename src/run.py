"""Orquesta el bot completo: lee datos -> detecta anomalías -> notifica.

Uso:
    python src/run.py                  # usa data/synthetic_metric.csv (lo genera si no existe)
    python src/run.py --generate       # regenera los datos sintéticos antes de detectar
    python src/run.py --plot           # guarda además un PNG con las anomalías marcadas
    python src/run.py --no-notify      # detecta pero no envía alertas (solo consola)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from anomaly import detect_anomalies
from generate_synthetic import generate_series
from generate_synthetic import save as save_synthetic
import notify as notify_module

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_data(config: dict, regenerate: bool) -> pd.DataFrame:
    data_path = ROOT / config["data"]["path"]
    if regenerate or not data_path.exists():
        print(f"Generando datos sintéticos en {data_path} ...")
        df = generate_series()
        save_synthetic(df, data_path)
    return pd.read_csv(data_path, parse_dates=["date"])


def plot_results(df: pd.DataFrame, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["date"], df["value"], label="valor", color="#2563eb")
    anomalies = df[df["is_anomaly"]]
    ax.scatter(
        anomalies["date"], anomalies["value"],
        color="#dc2626", zorder=5, label="anomalía detectada",
    )
    ax.set_title("Detección de anomalías")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Valor")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)
    print(f"Gráfico guardado en {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--generate", action="store_true", help="Regenera los datos sintéticos antes de detectar")
    parser.add_argument("--plot", action="store_true", help="Guarda un PNG con las anomalías marcadas")
    parser.add_argument("--no-notify", action="store_true", help="No envía alertas, solo muestra resultado en consola")
    args = parser.parse_args()

    config = load_config(args.config)
    df = load_data(config, args.generate)

    detection_cfg = config["detection"]
    result = detect_anomalies(
        df,
        value_col="value",
        window=detection_cfg["window_days"],
        threshold=detection_cfg["threshold_std"],
        method=detection_cfg.get("method", "zscore"),
        iqr_multiplier=detection_cfg.get("iqr_multiplier", 1.5),
    )

    anomalies = result[result["is_anomaly"]]
    print(f"\n{len(result)} días analizados, {len(anomalies)} marcados como anómalos:\n")
    if anomalies.empty:
        print("  (ninguno)")
    else:
        cols = ["date", "value", "expected_value"] + (["z_score"] if "z_score" in anomalies.columns else [])
        print(anomalies[cols].to_string(index=False))

    if args.plot:
        plot_results(result, ROOT / "data" / "detected_anomalies.png")

    if not args.no_notify and not anomalies.empty:
        metric_name = config["data"].get("metric_name", "métrica")
        messages = [
            notify_module.format_message(
                metric_name,
                row["date"].strftime("%Y-%m-%d"),
                row["value"],
                row.get("expected_value", float("nan")),
            )
            for _, row in anomalies.iterrows()
        ]
        notify_module.notify(messages, config)


if __name__ == "__main__":
    main()
