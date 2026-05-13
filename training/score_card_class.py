"""
E3 — Score-card per-class анализ.

Для каждого изображения датасета считаются 5 детерминированных метрик
(те же, что в `ml-service/app/classifier.py::_compute_scores`):
brightness, contrast, saturation, warmth, sharpness.

Затем строятся:
1. Радарные графики «сигнатуры» каждого класса в 5D-пространстве.
2. Violin plots по каждой метрике с разбивкой по классам.
3. Статистический тест (ANOVA + Kruskal–Wallis) — какие метрики реально
   разделяют классы.
4. Baseline-классификатор: только 5 score-card фич → логрег / RF →
   accuracy. Это нижняя планка точности «дёшевыми» признаками,
   с которой сравнивается полная нейросеть.

Запуск:
  python score_card_class.py \\
    --data-dir ./dataset \\
    --out-dir ./out/scorecard \\
    --splits train val

Артефакты:
  out/scorecard/scores.csv        — N строк, score-card по каждому изображению
  out/scorecard/stats.csv         — mean/std по 5 метрикам и 8 классам
  out/scorecard/radar.png         — 8 радарных чартов
  out/scorecard/violins.png       — 5 violin plot'ов
  out/scorecard/anova.json        — статистическая значимость каждой метрики
  out/scorecard/baseline.json     — accuracy / per-class F1 логрег'а и RF
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image

METRICS = ["brightness", "contrast", "saturation", "warmth", "sharpness"]


def compute_scores(img_path: Path) -> dict:
    """Идентичная копия `_compute_scores()` из ml-service/app/classifier.py.

    Дублирована намеренно: training/ не должен зависеть от ml-service/,
    чтобы скрипты были автономны для запуска из Colab.
    """
    img = Image.open(img_path).convert("RGB").resize((224, 224))
    arr = np.asarray(img).astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    luma = 0.299 * r + 0.587 * g + 0.114 * b

    brightness = float(luma.mean())
    contrast = float(min(luma.std() * 2.0, 1.0))

    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 1e-6, (mx - mn) / mx, 0.0)
    saturation = float(sat.mean())

    warmth = float(np.clip(((r - b).mean() + 1.0) / 2.0, 0.0, 1.0))

    gx = float(np.abs(np.diff(luma, axis=1)).mean())
    gy = float(np.abs(np.diff(luma, axis=0)).mean())
    sharpness = float(min((gx + gy) * 5.0, 1.0))

    return {
        "brightness": brightness, "contrast": contrast, "saturation": saturation,
        "warmth": warmth, "sharpness": sharpness,
    }


def iter_dataset(data_dir: Path, splits: list[str]):
    """Yields (image_path, class_name) для всех изображений в указанных сплитах."""
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    for split in splits:
        split_dir = data_dir / split
        if not split_dir.is_dir():
            continue
        for cls_dir in sorted(split_dir.iterdir()):
            if not cls_dir.is_dir():
                continue
            for img_path in cls_dir.iterdir():
                if img_path.suffix.lower() in exts:
                    yield img_path, cls_dir.name, split


def plot_radar(stats_by_class: dict[str, dict[str, float]], out_path: Path):
    """8 радарных чартов в одной фигуре."""
    import matplotlib.pyplot as plt
    classes = sorted(stats_by_class.keys())
    n = len(classes)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.5, rows * 3.5),
                             subplot_kw={"projection": "polar"})
    axes = axes.flatten() if n > 1 else [axes]

    angles = np.linspace(0, 2 * np.pi, len(METRICS), endpoint=False).tolist()
    angles += angles[:1]

    for ax, cls in zip(axes, classes):
        values = [stats_by_class[cls][m] for m in METRICS]
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2, color="#c0392b")
        ax.fill(angles, values, alpha=0.25, color="#c0392b")
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(METRICS, fontsize=8)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.25, 0.5, 0.75])
        ax.set_yticklabels(["0.25", "0.5", "0.75"], fontsize=6)
        ax.set_title(cls, fontsize=11, pad=10)
    # Гасим лишние оси
    for ax in axes[len(classes):]:
        ax.axis("off")
    fig.suptitle("Score-card сигнатура каждого класса (среднее по датасету)",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_violins(rows: list[dict], out_path: Path):
    """5 violin plot'ов: одна метрика — все классы."""
    import matplotlib.pyplot as plt
    classes = sorted({r["class"] for r in rows})
    fig, axes = plt.subplots(1, len(METRICS), figsize=(len(METRICS) * 3.2, 4),
                             sharey=True)
    for ax, metric in zip(axes, METRICS):
        data = [[r[metric] for r in rows if r["class"] == c] for c in classes]
        parts = ax.violinplot(data, showmedians=True)
        for pc in parts["bodies"]:
            pc.set_facecolor("#c0392b")
            pc.set_alpha(0.4)
        ax.set_xticks(range(1, len(classes) + 1))
        ax.set_xticklabels(classes, rotation=45, ha="right", fontsize=8)
        ax.set_title(metric, fontsize=10)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("score [0..1]")
    fig.suptitle("Распределение score-card метрик по классам", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def run_anova(rows: list[dict]) -> dict:
    """ANOVA + Kruskal-Wallis для каждой метрики."""
    from scipy.stats import f_oneway, kruskal
    classes = sorted({r["class"] for r in rows})
    out = {}
    for metric in METRICS:
        groups = [[r[metric] for r in rows if r["class"] == c] for c in classes]
        f_stat, f_p = f_oneway(*groups)
        h_stat, h_p = kruskal(*groups)
        out[metric] = {
            "anova_F": float(f_stat), "anova_p": float(f_p),
            "kruskal_H": float(h_stat), "kruskal_p": float(h_p),
        }
    return out


def run_baseline(rows: list[dict], out_path: Path) -> dict:
    """Логрег / RF на 5 score-card фичах. Baseline точности."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    train_rows = [r for r in rows if r["split"] == "train"]
    val_rows = [r for r in rows if r["split"] == "val"]
    if not val_rows:  # если разделение неявное — берём 80/20 на лету
        np.random.seed(42)
        idx = np.arange(len(rows))
        np.random.shuffle(idx)
        cut = int(0.8 * len(idx))
        train_rows = [rows[i] for i in idx[:cut]]
        val_rows = [rows[i] for i in idx[cut:]]

    def vec(r):
        return [r[m] for m in METRICS]

    X_tr = np.array([vec(r) for r in train_rows])
    y_tr = np.array([r["class"] for r in train_rows])
    X_va = np.array([vec(r) for r in val_rows])
    y_va = np.array([r["class"] for r in val_rows])

    results = {}
    for name, clf in [
        ("logreg", Pipeline([("scaler", StandardScaler()),
                             ("clf", LogisticRegression(max_iter=2000))])),
        ("random_forest", RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)),
    ]:
        clf.fit(X_tr, y_tr)
        pred = clf.predict(X_va)
        results[name] = {
            "accuracy": float(accuracy_score(y_va, pred)),
            "macro_f1": float(f1_score(y_va, pred, average="macro")),
            "weighted_f1": float(f1_score(y_va, pred, average="weighted")),
            "per_class": classification_report(y_va, pred, output_dict=True, zero_division=0),
        }

    return {
        "n_train": len(train_rows),
        "n_val": len(val_rows),
        "models": results,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--out-dir", default=Path("./out/scorecard"), type=Path)
    p.add_argument("--splits", nargs="+", default=["train", "val"])
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Computing score-card per image...")
    rows = []
    for i, (img_path, cls_name, split) in enumerate(iter_dataset(args.data_dir, args.splits), 1):
        try:
            scores = compute_scores(img_path)
        except Exception as e:
            print(f"  ! {img_path}: {e}")
            continue
        rows.append({
            "image": str(img_path),
            "class": cls_name,
            "split": split,
            **scores,
        })
        if i % 200 == 0:
            print(f"  processed {i}")

    print(f"Total: {len(rows)} images.")
    if not rows:
        print("No images found. Check --data-dir.")
        return

    # CSV дамп всех значений
    csv_path = args.out_dir / "scores.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "class", "split"] + METRICS)
        writer.writeheader()
        writer.writerows(rows)

    # Среднее/median/std по классам
    stats_by_class: dict[str, dict[str, float]] = {}
    stats_table = []
    classes = sorted({r["class"] for r in rows})
    for cls in classes:
        cls_rows = [r for r in rows if r["class"] == cls]
        means = {m: float(np.mean([r[m] for r in cls_rows])) for m in METRICS}
        stds = {m: float(np.std([r[m] for r in cls_rows])) for m in METRICS}
        meds = {m: float(np.median([r[m] for r in cls_rows])) for m in METRICS}
        stats_by_class[cls] = means
        stats_table.append({
            "class": cls,
            "count": len(cls_rows),
            **{f"{m}_mean": means[m] for m in METRICS},
            **{f"{m}_std": stds[m] for m in METRICS},
            **{f"{m}_median": meds[m] for m in METRICS},
        })
    with (args.out_dir / "stats.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stats_table[0].keys()))
        writer.writeheader()
        writer.writerows(stats_table)

    print("Plotting radar charts...")
    plot_radar(stats_by_class, args.out_dir / "radar.png")
    print("Plotting violin plots...")
    plot_violins(rows, args.out_dir / "violins.png")

    print("Running ANOVA + Kruskal-Wallis...")
    anova = run_anova(rows)
    (args.out_dir / "anova.json").write_text(json.dumps(anova, indent=2, ensure_ascii=False))
    for m, st in anova.items():
        sig = "***" if st["anova_p"] < 1e-10 else "**" if st["anova_p"] < 1e-3 else "*" if st["anova_p"] < 0.05 else "ns"
        print(f"  {m:11s} ANOVA F={st['anova_F']:8.2f} p={st['anova_p']:.2e} {sig}")

    print("Running baseline classifiers (5 hand-crafted features)...")
    baseline = run_baseline(rows, args.out_dir / "baseline.json")
    (args.out_dir / "baseline.json").write_text(json.dumps(baseline, indent=2, ensure_ascii=False))
    for name, res in baseline["models"].items():
        print(f"  {name:14s} acc={res['accuracy']:.3f}  macro_F1={res['macro_f1']:.3f}")

    print(f"\nDone. Artifacts in {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
