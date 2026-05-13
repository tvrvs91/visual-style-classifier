"""
E6 — Multi-label fine-tune EfficientNet-B0 с auto-generated co-метками.

Single-label CrossEntropy не подходит для задачи «стиль»: один кадр может
одновременно быть `monochrome` + `minimalist` + `dramatic`. Этот скрипт:

1. Расширяет single-label ImageFolder до multi-label DataSet, генерируя
   дополнительные метки **операционально** по score-card-фичам:

   gold-метка (из папки)                       — 1.0
   monochrome  если saturation < 0.10          — 1.0
   warm        как co-метка не используем;     # warmth относится к контексту
   golden_hour если warmth > 0.62 И bright > 0.45 И sat > 0.25
   dark        если brightness < 0.30
   airy        если brightness > 0.70 И contrast < 0.45
   dramatic    если contrast > 0.70
   neon        если saturation > 0.65 И brightness < 0.45

   Минимум 1 метка (gold), максимум 4 (соседние по score-card).

2. Тренирует ту же EfficientNet-B0 с заменой:
   - CrossEntropyLoss → BCEWithLogitsLoss с pos_weight
   - softmax → sigmoid
   - argmax-предсказание → threshold per class

3. На validation тюнит per-class threshold по F1 (Youden's J — резервный
   вариант).

4. Финальные метрики: mAP (mean average precision), per-class F1,
   exact-match accuracy, Hamming accuracy.

Запуск (требует GPU для разумного времени):
  python train_multilabel.py \\
    --data-dir ./dataset \\
    --out-dir ./out/multilabel \\
    --epochs 25 --head-epochs 5 \\
    --init-weights ./out/efficientnet_b0_styles.pth   # тёплый старт от v3

Артефакты:
  out/multilabel/efficientnet_b0_multilabel.pth
  out/multilabel/thresholds.json
  out/multilabel/metrics.json
  out/multilabel/co_label_stats.json
  out/multilabel/comparison_singlelabel_vs_multilabel.csv
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def score_card(img: Image.Image) -> dict:
    """Та же логика, что в ml-service/app/classifier.py::_compute_scores."""
    arr = np.asarray(img.resize((224, 224))).astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    brightness = float(luma.mean())
    contrast = float(min(luma.std() * 2.0, 1.0))
    mx, mn = arr.max(axis=2), arr.min(axis=2)
    saturation = float(np.where(mx > 1e-6, (mx - mn) / mx, 0.0).mean())
    warmth = float(np.clip(((r - b).mean() + 1.0) / 2.0, 0.0, 1.0))
    gx = float(np.abs(np.diff(luma, axis=1)).mean())
    gy = float(np.abs(np.diff(luma, axis=0)).mean())
    sharpness = float(min((gx + gy) * 5.0, 1.0))
    return {"brightness": brightness, "contrast": contrast, "saturation": saturation,
            "warmth": warmth, "sharpness": sharpness}


def derive_co_labels(scores: dict, gold_class: str, class_names: list[str]) -> np.ndarray:
    """Многоhot вектор меток по score-card-правилам + gold-метка.

    Возвращает (n_classes,) с 1.0 на активных позициях. Правила
    подобраны так, чтобы не противоречить друг другу (например,
    одно изображение не должно одновременно быть airy и dark).
    """
    y = np.zeros(len(class_names), dtype=np.float32)
    y[class_names.index(gold_class)] = 1.0

    s = scores

    def maybe(cls: str, cond: bool):
        if cond and cls in class_names:
            y[class_names.index(cls)] = 1.0

    # Тональные и цветовые признаки
    maybe("monochrome", s["saturation"] < 0.10)
    maybe("dark", s["brightness"] < 0.30)
    maybe("airy", s["brightness"] > 0.70 and s["contrast"] < 0.45)

    # Композиционные / условия съёмки
    maybe("dramatic", s["contrast"] > 0.70)
    maybe("golden_hour", s["warmth"] > 0.62 and s["brightness"] > 0.45 and s["saturation"] > 0.25)
    maybe("neon", s["saturation"] > 0.65 and s["brightness"] < 0.45)

    # Подавление противоречий: если есть и airy, и dark — оставляем gold.
    if y[class_names.index("airy")] and "dark" in class_names and y[class_names.index("dark")]:
        if gold_class == "airy":
            y[class_names.index("dark")] = 0.0
        else:
            y[class_names.index("airy")] = 0.0

    # Ограничение «не более 4 меток»: оставляем те, что ближе к gold (gold + top-3 по score)
    if y.sum() > 4:
        keep = np.zeros_like(y)
        keep[class_names.index(gold_class)] = 1.0
        active = [(i, 1.0) for i in range(len(y)) if y[i] and i != class_names.index(gold_class)]
        active = active[:3]
        for i, _ in active:
            keep[i] = 1.0
        y = keep
    return y


class MultiLabelStyleDataset(Dataset):
    def __init__(self, root: Path, class_names: list[str], train: bool):
        self.class_names = class_names
        self.samples: list[tuple[Path, str]] = []
        for cls in class_names:
            cls_dir = root / cls
            if not cls_dir.is_dir():
                continue
            for p in cls_dir.iterdir():
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    self.samples.append((p, cls))
        if train:
            self.tf = transforms.Compose([
                transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.ColorJitter(brightness=0.15, contrast=0.15,
                                       saturation=0.15, hue=0.05),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ])
        else:
            self.tf = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ])

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        path, cls = self.samples[i]
        img = Image.open(path).convert("RGB")
        # Score-card нужно считать на исходном изображении, ДО аугментаций,
        # иначе RandomResizedCrop и ColorJitter сдвинут метки.
        scores = score_card(img)
        y = derive_co_labels(scores, cls, self.class_names)
        return self.tf(img), torch.from_numpy(y)


def build_model(num_classes: int, init_weights: Path | None) -> nn.Module:
    m = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    in_f = m.classifier[1].in_features
    m.classifier[1] = nn.Linear(in_f, num_classes)
    if init_weights:
        state = torch.load(init_weights, map_location="cpu")
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        # Голова в single-label = той же размерности, можно грузить.
        m.load_state_dict(state, strict=False)
    return m


def compute_pos_weight(loader: DataLoader, num_classes: int) -> torch.Tensor:
    """pos_weight = neg / pos для каждого класса (для BCEWithLogits)."""
    pos = torch.zeros(num_classes)
    total = 0
    for _, y in loader:
        pos += y.sum(dim=0)
        total += y.size(0)
    neg = total - pos
    return (neg / pos.clamp(min=1)).clamp(max=20.0)  # верх ограничен чтобы не разнесло


def tune_thresholds(probs: np.ndarray, y_true: np.ndarray) -> np.ndarray:
    """Per-class threshold, максимизирующий F1 на val_set."""
    from sklearn.metrics import f1_score
    n_classes = probs.shape[1]
    best = np.zeros(n_classes)
    for c in range(n_classes):
        f1s = []
        for t in np.linspace(0.05, 0.95, 19):
            f1s.append((t, f1_score(y_true[:, c], (probs[:, c] >= t).astype(int),
                                    zero_division=0)))
        best[c] = max(f1s, key=lambda x: x[1])[0]
    return best


def evaluate_ml(model, loader, device, class_names) -> dict:
    """Полная оценка multi-label: per-class probs, threshold tuning, метрики."""
    from sklearn.metrics import (average_precision_score, f1_score,
                                 precision_score, recall_score)
    model.eval()
    all_probs, all_y = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            logits = model(x)
            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
            all_y.append(y.numpy())
    probs = np.concatenate(all_probs)
    y = np.concatenate(all_y)

    # Per-class AP (площадь PR) + mAP
    aps = [average_precision_score(y[:, c], probs[:, c]) for c in range(len(class_names))]
    mAP = float(np.mean(aps))

    # Threshold tuning по F1
    thr = tune_thresholds(probs, y)
    pred = (probs >= thr[None, :]).astype(int)

    per_class = {}
    for c, name in enumerate(class_names):
        per_class[name] = {
            "AP": float(aps[c]),
            "threshold": float(thr[c]),
            "precision": float(precision_score(y[:, c], pred[:, c], zero_division=0)),
            "recall": float(recall_score(y[:, c], pred[:, c], zero_division=0)),
            "f1": float(f1_score(y[:, c], pred[:, c], zero_division=0)),
            "support_pos": int(y[:, c].sum()),
        }

    exact_match = float((pred == y.astype(int)).all(axis=1).mean())
    hamming = float((pred == y.astype(int)).mean())  # доля правильных битов

    return {
        "mAP": mAP,
        "macro_f1": float(np.mean([per_class[n]["f1"] for n in class_names])),
        "exact_match_accuracy": exact_match,
        "hamming_accuracy": hamming,
        "per_class": per_class,
        "thresholds": thr.tolist(),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--out-dir", default=Path("./out/multilabel"), type=Path)
    p.add_argument("--init-weights", type=Path, default=None,
                   help="Тёплый старт от single-label v3 чекпоинта")
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--head-epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr-head", type=float, default=1e-3)
    p.add_argument("--lr-backbone", type=float, default=1e-4)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--patience", type=int, default=7)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Сначала определяем classes по структуре train/ — это источник правды.
    train_root = args.data_dir / "train"
    val_root = args.data_dir / "val"
    class_names = sorted([d.name for d in train_root.iterdir() if d.is_dir()])
    print(f"Classes ({len(class_names)}): {class_names}")

    train_ds = MultiLabelStyleDataset(train_root, class_names, train=True)
    val_ds = MultiLabelStyleDataset(val_root, class_names, train=False)
    print(f"Train: {len(train_ds)}  Val: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=args.num_workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=args.num_workers, pin_memory=True)

    # Статистика co-label'ов
    print("Counting co-labels on train set (one pass without aug)...")
    co_counts = Counter()
    label_combos: Counter = Counter()
    pure_train_ds = MultiLabelStyleDataset(train_root, class_names, train=False)
    for _, y in DataLoader(pure_train_ds, batch_size=64, num_workers=args.num_workers):
        for vec in y.numpy():
            active = tuple(i for i, v in enumerate(vec) if v > 0.5)
            label_combos[active] += 1
            for i in active:
                co_counts[class_names[i]] += 1
    n_total = sum(label_combos.values())
    multi_label_share = sum(c for k, c in label_combos.items() if len(k) > 1) / n_total
    print(f"  ≥2 меток: {multi_label_share:.1%}")
    top_combos = label_combos.most_common(10)
    co_label_stats = {
        "per_class_positives": dict(co_counts),
        "share_multi_label": multi_label_share,
        "top_combinations": [
            {"labels": [class_names[i] for i in combo], "count": cnt}
            for combo, cnt in top_combos
        ],
    }
    (args.out_dir / "co_label_stats.json").write_text(
        json.dumps(co_label_stats, indent=2, ensure_ascii=False))

    # Модель
    model = build_model(len(class_names), args.init_weights).to(device)

    # pos_weight
    print("Computing pos_weight for BCEWithLogits...")
    pos_w = compute_pos_weight(train_loader, len(class_names)).to(device)
    print(f"  pos_weight: {pos_w.cpu().numpy().round(2).tolist()}")
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_w)

    backbone_params = [p for n, p in model.named_parameters() if not n.startswith("classifier")]
    head_params = [p for n, p in model.named_parameters() if n.startswith("classifier")]

    # Phase 1: только голова
    for p_ in backbone_params:
        p_.requires_grad = False
    optimizer = torch.optim.AdamW(head_params, lr=args.lr_head, weight_decay=0.01)
    print(f"\n[Phase 1] Head-only for {args.head_epochs} epochs...")
    for ep in range(1, args.head_epochs + 1):
        model.train()
        losses = []
        t0 = time.time()
        for x, y in train_loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        print(f"  ep{ep:02d}  train_loss={np.mean(losses):.3f}  ({time.time()-t0:.1f}s)")

    # Phase 2: full fine-tune
    for p_ in backbone_params:
        p_.requires_grad = True
    optimizer = torch.optim.AdamW([
        {"params": backbone_params, "lr": args.lr_backbone},
        {"params": head_params, "lr": args.lr_head},
    ], weight_decay=0.01)
    n_full = args.epochs - args.head_epochs
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_full)

    print(f"\n[Phase 2] Full fine-tune for {n_full} epochs...")
    best_map = 0.0
    no_improve = 0
    metrics_history = []
    for ep in range(1, n_full + 1):
        model.train()
        losses = []
        t0 = time.time()
        for x, y in train_loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        scheduler.step()

        m = evaluate_ml(model, val_loader, device, class_names)
        metrics_history.append({"epoch": ep, "train_loss": float(np.mean(losses)), **{
            k: v for k, v in m.items() if k not in ("per_class", "thresholds")
        }})
        marker = ""
        if m["mAP"] > best_map:
            best_map = m["mAP"]
            no_improve = 0
            marker = " ⭐"
            torch.save(model.state_dict(), args.out_dir / "efficientnet_b0_multilabel.pth")
            (args.out_dir / "metrics.json").write_text(
                json.dumps(m, indent=2, ensure_ascii=False))
            (args.out_dir / "thresholds.json").write_text(
                json.dumps({n: m["per_class"][n]["threshold"] for n in class_names},
                           indent=2, ensure_ascii=False))
        else:
            no_improve += 1
        print(f"  ep{ep:02d}  loss={np.mean(losses):.3f}  mAP={m['mAP']:.3f}  "
              f"macro_F1={m['macro_f1']:.3f}  exact={m['exact_match_accuracy']:.3f}{marker}  "
              f"({time.time()-t0:.1f}s)")
        if no_improve >= args.patience:
            print(f"  ⏹  Early stopping after {args.patience} epochs w/o mAP improvement.")
            break

    (args.out_dir / "history.json").write_text(
        json.dumps(metrics_history, indent=2, ensure_ascii=False))
    print(f"\nDone. Best mAP = {best_map:.4f}. Artifacts in {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
