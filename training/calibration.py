"""
E4 — Калибровка вероятностей через temperature scaling.

Реализует методологию Guo et al. 2017 «On Calibration of Modern Neural Networks»:
1. Считаем baseline ECE/MCE/Brier/NLL на val_set.
2. Оптимизируем единый скаляр T (logits / T) так, чтобы минимизировать
   NLL на том же val_set (LBFGS).
3. Перерисовываем reliability diagram, считаем метрики после.
4. Опционально — vector scaling (per-class temperature).

Запуск:
  python calibration.py \\
    --weights ./out/efficientnet_b0_styles.pth \\
    --data-dir ./dataset \\
    --out-dir ./out/calibration \\
    --vector-scaling

Артефакты:
  out/calibration/logits.npy         — сырые logits (N, C)
  out/calibration/labels.npy         — метки (N,)
  out/calibration/metrics.json       — все метрики до и после
  out/calibration/temperature.txt    — найденный T (для деплоя в ml-service)
  out/calibration/reliability_before.png
  out/calibration/reliability_after.png
  out/calibration/reliability_combined.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import efficientnet_b0

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_eval_transform():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def load_model(weights_path: Path, num_classes: int, device: torch.device) -> nn.Module:
    m = efficientnet_b0(weights=None)
    in_f = m.classifier[1].in_features
    m.classifier[1] = nn.Linear(in_f, num_classes)
    state = torch.load(weights_path, map_location=device)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    m.load_state_dict(state)
    m.eval().to(device)
    return m


def collect_logits(model: nn.Module, dataset, device: torch.device,
                   batch_size: int = 32) -> tuple[np.ndarray, np.ndarray]:
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=2)
    all_l, all_y = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            all_l.append(model(x).cpu().numpy())
            all_y.append(y.numpy())
    return np.concatenate(all_l), np.concatenate(all_y)


# -------------------- метрики калибровки -----------------------------------

def expected_calibration_error(probs: np.ndarray, y: np.ndarray, n_bins: int = 15):
    """ECE по равномерным бакетам confidence ∈ [0, 1].

    Возвращает (ECE, MCE, bins) где bins — список (lo, hi, avg_conf, accuracy, count)
    для построения reliability diagram.
    """
    confs = probs.max(axis=1)
    preds = probs.argmax(axis=1)
    correct = (preds == y).astype(np.float32)

    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    mce = 0.0
    bin_stats = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (confs > lo) & (confs <= hi) if i > 0 else (confs >= lo) & (confs <= hi)
        n = mask.sum()
        if n == 0:
            bin_stats.append({"lo": float(lo), "hi": float(hi), "avg_conf": 0.0,
                              "accuracy": 0.0, "count": 0})
            continue
        avg_conf = float(confs[mask].mean())
        acc = float(correct[mask].mean())
        bin_gap = abs(avg_conf - acc)
        ece += (n / len(y)) * bin_gap
        mce = max(mce, bin_gap)
        bin_stats.append({"lo": float(lo), "hi": float(hi), "avg_conf": avg_conf,
                          "accuracy": acc, "count": int(n)})
    return float(ece), float(mce), bin_stats


def brier_score(probs: np.ndarray, y: np.ndarray) -> float:
    """Многоклассовый Brier score: средний squared error от one-hot."""
    one_hot = np.eye(probs.shape[1])[y]
    return float(((probs - one_hot) ** 2).sum(axis=1).mean())


def nll(probs: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> float:
    return float(-np.log(probs[np.arange(len(y)), y] + eps).mean())


def all_metrics(probs: np.ndarray, y: np.ndarray) -> dict:
    ece, mce, bins = expected_calibration_error(probs, y, n_bins=15)
    return {
        "accuracy": float((probs.argmax(axis=1) == y).mean()),
        "mean_confidence": float(probs.max(axis=1).mean()),
        "ECE": ece,
        "MCE": mce,
        "Brier": brier_score(probs, y),
        "NLL": nll(probs, y),
        "bins": bins,
    }


# -------------------- temperature scaling ----------------------------------

def fit_temperature(logits: np.ndarray, y: np.ndarray, device: torch.device,
                    init: float = 1.0, max_iter: int = 200) -> float:
    """Оптимизация одного скаляра T через LBFGS, минимизируя NLL."""
    L = torch.from_numpy(logits).float().to(device)
    Y = torch.from_numpy(y).long().to(device)
    T = torch.nn.Parameter(torch.tensor([init], device=device))
    optimizer = optim.LBFGS([T], lr=0.1, max_iter=max_iter)

    def closure():
        optimizer.zero_grad()
        loss = F.cross_entropy(L / T, Y)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(T.detach().cpu().item())


def fit_vector_temperature(logits: np.ndarray, y: np.ndarray, device: torch.device,
                           max_iter: int = 200) -> np.ndarray:
    """Per-class temperature: один скаляр на каждый класс. Гибче, но переоптимизирует
    на маленьких val_set."""
    n_classes = logits.shape[1]
    L = torch.from_numpy(logits).float().to(device)
    Y = torch.from_numpy(y).long().to(device)
    T = torch.nn.Parameter(torch.ones(n_classes, device=device))
    optimizer = optim.LBFGS([T], lr=0.05, max_iter=max_iter)

    def closure():
        optimizer.zero_grad()
        loss = F.cross_entropy(L / T.clamp(min=0.05), Y)
        loss.backward()
        return loss

    optimizer.step(closure)
    return T.detach().clamp(min=0.05).cpu().numpy()


# -------------------- visualisation ----------------------------------------

def plot_reliability(bins_before: list[dict], bins_after: list[dict] | None,
                     out_path: Path, title_extra: str = ""):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2 if bins_after else 1,
                             figsize=(11 if bins_after else 5.5, 4.5))
    if not bins_after:
        axes = [axes]

    def _bar(ax, bins, title):
        widths = [b["hi"] - b["lo"] for b in bins]
        centers = [(b["hi"] + b["lo"]) / 2 for b in bins]
        accs = [b["accuracy"] for b in bins]
        confs = [b["avg_conf"] for b in bins]
        ax.bar(centers, accs, width=widths, edgecolor="black", color="#c0392b",
               alpha=0.7, label="empirical accuracy")
        ax.bar(centers, [c - a for c, a in zip(confs, accs)],
               width=widths, bottom=accs, color="#888", alpha=0.4, label="gap (overconfidence)")
        ax.plot([0, 1], [0, 1], "--", color="black", linewidth=1, label="perfect calibration")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xlabel("confidence"); ax.set_ylabel("accuracy")
        ax.set_title(title)
        ax.legend(loc="upper left", fontsize=8, frameon=False)

    _bar(axes[0], bins_before, f"Before {title_extra}")
    if bins_after:
        _bar(axes[1], bins_after, f"After {title_extra}")

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True, type=Path)
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--out-dir", default=Path("./out/calibration"), type=Path)
    p.add_argument("--split", default="val")
    p.add_argument("--vector-scaling", action="store_true")
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    eval_tf = build_eval_transform()
    ds = datasets.ImageFolder(args.data_dir / args.split, transform=eval_tf)
    class_names = ds.classes
    print(f"Classes: {class_names}")
    print(f"Split '{args.split}': {len(ds)} images")

    model = load_model(args.weights, len(class_names), device)

    print("Collecting logits on val_set...")
    logits, y = collect_logits(model, ds, device)
    np.save(args.out_dir / "logits.npy", logits)
    np.save(args.out_dir / "labels.npy", y)
    print(f"  logits shape: {logits.shape}")

    # До калибровки
    probs_before = torch.softmax(torch.from_numpy(logits), dim=1).numpy()
    m_before = all_metrics(probs_before, y)
    print(f"\nBEFORE calibration:")
    print(f"  acc={m_before['accuracy']:.4f}  mean_conf={m_before['mean_confidence']:.4f}")
    print(f"  ECE={m_before['ECE']:.4f}  MCE={m_before['MCE']:.4f}  "
          f"Brier={m_before['Brier']:.4f}  NLL={m_before['NLL']:.4f}")

    # Scalar temperature
    print("\nFitting scalar temperature T (LBFGS, NLL objective)...")
    T = fit_temperature(logits, y, device)
    print(f"  T* = {T:.4f}")
    probs_T = torch.softmax(torch.from_numpy(logits) / T, dim=1).numpy()
    m_after_T = all_metrics(probs_T, y)
    print(f"AFTER scalar scaling:")
    print(f"  acc={m_after_T['accuracy']:.4f}  mean_conf={m_after_T['mean_confidence']:.4f}")
    print(f"  ECE={m_after_T['ECE']:.4f}  MCE={m_after_T['MCE']:.4f}  "
          f"Brier={m_after_T['Brier']:.4f}  NLL={m_after_T['NLL']:.4f}")

    (args.out_dir / "temperature.txt").write_text(f"{T:.6f}\n")
    plot_reliability(m_before["bins"], m_after_T["bins"],
                     args.out_dir / "reliability_combined.png",
                     title_extra=f"(T={T:.3f})")
    plot_reliability(m_before["bins"], None,
                     args.out_dir / "reliability_before.png")
    plot_reliability(m_after_T["bins"], None,
                     args.out_dir / "reliability_after.png",
                     title_extra=f"(T={T:.3f})")

    result = {
        "scalar_temperature": float(T),
        "before": {k: v for k, v in m_before.items() if k != "bins"},
        "after_scalar": {k: v for k, v in m_after_T.items() if k != "bins"},
    }

    # Vector scaling (опционально)
    if args.vector_scaling:
        print("\nFitting vector temperature (per-class)...")
        Tv = fit_vector_temperature(logits, y, device)
        print(f"  Tv = {Tv}")
        scaled = logits / Tv[None, :]
        probs_Tv = torch.softmax(torch.from_numpy(scaled), dim=1).numpy()
        m_after_Tv = all_metrics(probs_Tv, y)
        print(f"AFTER vector scaling:")
        print(f"  ECE={m_after_Tv['ECE']:.4f}  NLL={m_after_Tv['NLL']:.4f}  "
              f"Brier={m_after_Tv['Brier']:.4f}")
        result["vector_temperature"] = Tv.tolist()
        result["after_vector"] = {k: v for k, v in m_after_Tv.items() if k != "bins"}
        np.savetxt(args.out_dir / "temperature_vector.csv", Tv[None, :], fmt="%.6f",
                   delimiter=",", header=",".join(class_names), comments="")

    (args.out_dir / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nDone. Artifacts in {args.out_dir.resolve()}")
    print(f"  Внести в ml-service: разделить logits на T = {T:.4f} перед softmax.")


if __name__ == "__main__":
    main()
