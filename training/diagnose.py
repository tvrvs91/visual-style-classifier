"""
Диагностика обученной модели на validation set.

Выдаёт:
- per-class precision / recall / F1
- топ-10 пар «модель сказала X, на самом деле Y»
- confusion matrix CSV + PNG
- распределение топ-1 предсказаний (показывает bias на доминирующий класс)

Использование:
  python diagnose.py --weights efficientnet_b0_styles.pth \
                     --val-dir ./dataset/val \
                     --arch efficientnet_b0
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import efficientnet_b0, resnet50

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_model(arch: str, num_classes: int) -> nn.Module:
    if arch == "efficientnet_b0":
        m = efficientnet_b0(weights=None)
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, num_classes)
    elif arch == "resnet50":
        m = resnet50(weights=None)
        m.fc = nn.Linear(m.fc.in_features, num_classes)
    else:
        raise ValueError(f"unknown arch: {arch}")
    return m


def load_weights(model: nn.Module, path: str, device):
    state = torch.load(path, map_location=device, weights_only=False)
    if isinstance(state, nn.Module):
        state = state.state_dict()
    elif isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    model.load_state_dict(state, strict=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--val-dir", required=True, help="Папка вида val/{class}/*.jpg")
    ap.add_argument("--arch", choices=["efficientnet_b0", "resnet50"], default="efficientnet_b0")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--out-dir", default="./diag_out")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    ds = datasets.ImageFolder(args.val_dir, transform=tf)
    classes = ds.classes
    print(f"Validation: {len(ds)} фото, {len(classes)} классов: {classes}")

    model = build_model(args.arch, len(classes)).to(device)
    load_weights(model, args.weights, device)
    model.eval()

    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    all_y, all_pred, all_prob = [], [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            logits = model(x)
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            preds = probs.argmax(1)
            all_y.extend(y.numpy())
            all_pred.extend(preds)
            all_prob.append(probs)
    all_prob = np.concatenate(all_prob)

    # 1. Per-class report
    print("\n=== Per-class report ===")
    report = classification_report(all_y, all_pred, target_names=classes, digits=3, zero_division=0)
    print(report)
    (out / "classification_report.txt").write_text(report)

    # 2. Распределение предсказаний (bias detector)
    print("=== Распределение топ-1 предсказаний ===")
    pred_counts = Counter(all_pred)
    true_counts = Counter(all_y)
    print(f"{'class':<14} {'true':>7} {'pred':>7} {'ratio':>7}")
    for i, c in enumerate(classes):
        t = true_counts.get(i, 0)
        p = pred_counts.get(i, 0)
        ratio = p / max(t, 1)
        marker = " ⚠ over-predicted" if ratio > 1.5 else " ⚠ under-predicted" if ratio < 0.5 else ""
        print(f"{c:<14} {t:>7} {p:>7} {ratio:>7.2f}{marker}")

    # 3. Топ-10 путаниц
    print("\n=== Топ-10 путаниц ===")
    print("Формат: TRUE → PRED   (count)")
    confusions = []
    for true_i, pred_i in zip(all_y, all_pred):
        if true_i != pred_i:
            confusions.append((classes[true_i], classes[pred_i]))
    for (t, p), n in Counter(confusions).most_common(10):
        print(f"  {t:<14} → {p:<14} ({n})")

    # 4. Confusion matrix
    cm = confusion_matrix(all_y, all_pred)
    np.savetxt(out / "confusion_matrix.csv", cm, fmt="%d", delimiter=",",
               header=",".join(classes), comments="")

    try:
        import matplotlib.pyplot as plt
        # Нормализованная по строкам версия (показывает recall наглядно)
        cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True).clip(min=1)
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for ax, mat, title, fmt in [
            (axes[0], cm, "Confusion matrix (counts)", "d"),
            (axes[1], cm_norm, "Confusion matrix (row-normalized)", ".2f"),
        ]:
            im = ax.imshow(mat, cmap="Reds")
            ax.set_xticks(range(len(classes))); ax.set_yticks(range(len(classes)))
            ax.set_xticklabels(classes, rotation=45, ha="right")
            ax.set_yticklabels(classes)
            ax.set_xlabel("Predicted"); ax.set_ylabel("True")
            ax.set_title(title)
            for i in range(len(classes)):
                for j in range(len(classes)):
                    v = mat[i, j]
                    text = format(v, fmt)
                    ax.text(j, i, text, ha="center", va="center",
                            color="white" if v > mat.max() / 2 else "black", fontsize=8)
            fig.colorbar(im, ax=ax, fraction=0.046)
        fig.tight_layout()
        fig.savefig(out / "confusion_matrix.png", dpi=140)
        plt.close(fig)
        print(f"\n✓ Сохранено: {out/'confusion_matrix.png'}")
    except ImportError:
        pass

    # 5. Распределение confidence — индикатор калибровки
    top1_conf = all_prob.max(axis=1)
    print(f"\n=== Confidence на правильных vs неправильных ===")
    correct_mask = np.array(all_y) == np.array(all_pred)
    if correct_mask.sum() > 0:
        print(f"  правильные: mean conf = {top1_conf[correct_mask].mean():.3f}, "
              f"median = {np.median(top1_conf[correct_mask]):.3f}")
    if (~correct_mask).sum() > 0:
        print(f"  неправильные: mean conf = {top1_conf[~correct_mask].mean():.3f}, "
              f"median = {np.median(top1_conf[~correct_mask]):.3f}")
    if correct_mask.sum() and (~correct_mask).sum():
        gap = top1_conf[correct_mask].mean() - top1_conf[~correct_mask].mean()
        print(f"  gap: {gap:.3f}  (если < 0.1 — модель переуверенна, нужно label smoothing / TTA)")

    print(f"\nВсе артефакты в {out.resolve()}")


if __name__ == "__main__":
    main()
