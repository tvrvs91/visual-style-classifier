"""
Улучшенный training pipeline для фотостильной классификации.

Запускается как Python-скрипт ИЛИ копируется блоками в Colab-ячейки.

Что улучшено по сравнению с базовым fine-tuning'ом:
1. Балансировка классов через WeightedRandomSampler — лечит bias на доминирующий класс.
2. Двухфазный fine-tuning: сначала голова с замороженным backbone, потом всё целиком.
3. Cosine annealing scheduler — плавное снижение LR, обычно даёт +1-3 пп.
4. Label smoothing 0.1 — модель меньше уверена в крайностях, лучше калибрована.
5. Сильная, но безопасная для стиля аугментация (без grayscale, без сильного hue jitter).
6. Mixed precision на GPU — быстрее в 1.5-2 раза при той же точности.
7. Сохранение полного отчёта: best.pth, metrics.json, classification_report.txt,
   confusion_matrix.png — всё что нужно для диплома и для деплоя.

Использование:
  python train.py --data-dir ./dataset --arch efficientnet_b0 --epochs 25
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, transforms
from torchvision.models import (
    EfficientNet_B0_Weights,
    ResNet50_Weights,
    efficientnet_b0,
    resnet50,
)

# --- препроцессинг -----------------------------------------------------------

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_transforms():
    """Аугментация на train, чистый resize на val/test."""
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.7, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        # Аккуратно с цветом: hue=0.05 чтобы не испортить golden_hour;
        # никакого RandomGrayscale — он уничтожит warmth-сигнал.
        transforms.ColorJitter(brightness=0.15, contrast=0.15,
                               saturation=0.15, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])
    return train_tf, eval_tf


# --- архитектура -------------------------------------------------------------

def build_model(arch: str, num_classes: int) -> nn.Module:
    if arch == "efficientnet_b0":
        m = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
        in_f = m.classifier[1].in_features
        m.classifier[1] = nn.Linear(in_f, num_classes)
        backbone_params = [p for n, p in m.named_parameters() if not n.startswith("classifier")]
        head_params = [p for n, p in m.named_parameters() if n.startswith("classifier")]
    elif arch == "resnet50":
        m = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
        in_f = m.fc.in_features
        m.fc = nn.Linear(in_f, num_classes)
        backbone_params = [p for n, p in m.named_parameters() if not n.startswith("fc")]
        head_params = [p for n, p in m.named_parameters() if n.startswith("fc")]
    else:
        raise ValueError(f"unsupported arch: {arch}")
    return m, backbone_params, head_params


# --- балансировка ------------------------------------------------------------

def make_weighted_sampler(targets: list[int]) -> WeightedRandomSampler:
    """Каждый класс получает одинаковый ожидаемый вес в минибатче."""
    counts = Counter(targets)
    class_weights = {cls: 1.0 / cnt for cls, cnt in counts.items()}
    sample_weights = [class_weights[t] for t in targets]
    return WeightedRandomSampler(sample_weights, num_samples=len(targets), replacement=True)


# --- эпоха обучения ----------------------------------------------------------

def mixup_batch(x: torch.Tensor, y: torch.Tensor, alpha: float):
    """Mixup-аугментация: смешивает пары примеров. Возвращает (x_mix, y_a, y_b, lam)."""
    if alpha <= 0:
        return x, y, y, 1.0
    lam = float(np.random.beta(alpha, alpha))
    perm = torch.randperm(x.size(0), device=x.device)
    x_mix = lam * x + (1 - lam) * x[perm]
    return x_mix, y, y[perm], lam


def run_epoch(model, loader, criterion, optimizer, device, scaler, train: bool, mixup_alpha: float = 0.0):
    model.train(train)
    losses, correct, total = [], 0, 0
    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        if train:
            optimizer.zero_grad(set_to_none=True)
            x_in, y_a, y_b, lam = mixup_batch(x, y, mixup_alpha) if mixup_alpha > 0 else (x, y, y, 1.0)
            with torch.amp.autocast(device_type=device.type, enabled=scaler is not None):
                logits = model(x_in)
                loss = lam * criterion(logits, y_a) + (1 - lam) * criterion(logits, y_b)
            if scaler:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                optimizer.step()
        else:
            with torch.no_grad(), torch.amp.autocast(device_type=device.type, enabled=scaler is not None):
                logits = model(x)
                loss = criterion(logits, y)
        losses.append(loss.item())
        # accuracy при mixup считается против ИСХОДНЫХ y (не идеально, но
        # достаточно как индикатор; honest val acc меряется на val_loader)
        correct += (logits.argmax(1) == y).sum().item()
        total += y.size(0)
    return float(np.mean(losses)), correct / total


# --- репорты -----------------------------------------------------------------

def evaluate_full(model, loader, device, class_names, out_dir: Path):
    """Confusion matrix + classification report — для диагностики."""
    model.eval()
    all_y, all_pred = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            pred = model(x).argmax(1).cpu().numpy()
            all_y.extend(y.numpy())
            all_pred.extend(pred)

    report = classification_report(all_y, all_pred, target_names=class_names, digits=3, zero_division=0)
    (out_dir / "classification_report.txt").write_text(report)
    print("\n" + report)

    cm = confusion_matrix(all_y, all_pred)
    np.savetxt(out_dir / "confusion_matrix.csv", cm, fmt="%d", delimiter=",",
               header=",".join(class_names), comments="")

    # Опциональная картинка — если есть matplotlib
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(cm, cmap="Reds")
        ax.set_xticks(range(len(class_names)))
        ax.set_yticks(range(len(class_names)))
        ax.set_xticklabels(class_names, rotation=45, ha="right")
        ax.set_yticklabels(class_names)
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
        for i in range(len(class_names)):
            for j in range(len(class_names)):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046)
        fig.tight_layout()
        fig.savefig(out_dir / "confusion_matrix.png", dpi=140)
        plt.close(fig)
    except ImportError:
        pass


# --- main --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True,
                   help="Корень датасета с подпапками train/ и val/")
    p.add_argument("--out-dir", default="./out")
    p.add_argument("--arch", choices=["efficientnet_b0", "resnet50"], default="efficientnet_b0")
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--head-epochs", type=int, default=5,
                   help="Сколько эпох в первой фазе (только голова, backbone заморожен)")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr-head", type=float, default=1e-3)
    p.add_argument("--lr-backbone", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=0.01)
    p.add_argument("--label-smoothing", type=float, default=0.1)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--patience", type=int, default=7,
                   help="Early stopping: остановиться если val acc не улучшается N эпох")
    p.add_argument("--mixup-alpha", type=float, default=0.0,
                   help="Mixup beta-параметр (0 = выкл; 0.2-0.4 — типичные значения)")
    args = p.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Датасет ----------------------------------------------------------------
    train_tf, eval_tf = build_transforms()
    train_ds = datasets.ImageFolder(Path(args.data_dir) / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(Path(args.data_dir) / "val", transform=eval_tf)

    class_names = train_ds.classes
    num_classes = len(class_names)
    print(f"Classes ({num_classes}): {class_names}")
    print(f"class_to_idx: {train_ds.class_to_idx}")

    counts = Counter(t for _, t in train_ds.samples)
    print("Train counts per class:")
    for cls, idx in train_ds.class_to_idx.items():
        print(f"  {cls:14s} {counts[idx]:5d}")

    # Сохраняем маппинг — это критично для деплоя
    (out_dir / "class_to_idx.json").write_text(
        json.dumps(train_ds.class_to_idx, indent=2, ensure_ascii=False)
    )

    # Балансировка классов через WeightedRandomSampler
    sampler = make_weighted_sampler([t for _, t in train_ds.samples])

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, sampler=sampler,
                              num_workers=args.num_workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=args.num_workers, pin_memory=True)

    # Модель -----------------------------------------------------------------
    model, backbone_params, head_params = build_model(args.arch, num_classes)
    model = model.to(device)

    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    scaler = torch.amp.GradScaler() if device.type == "cuda" else None

    # Фаза 1 — только голова -------------------------------------------------
    for p_ in backbone_params:
        p_.requires_grad = False
    optimizer = optim.AdamW(head_params, lr=args.lr_head, weight_decay=args.weight_decay)
    print(f"\n[Phase 1] Training head only for {args.head_epochs} epochs...")
    metrics = []
    for ep in range(1, args.head_epochs + 1):
        t0 = time.time()
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, optimizer, device, scaler, train=True)
        vl_loss, vl_acc = run_epoch(model, val_loader, criterion, optimizer, device, scaler, train=False)
        dt = time.time() - t0
        metrics.append({"phase": 1, "epoch": ep, "train_loss": tr_loss, "train_acc": tr_acc,
                        "val_loss": vl_loss, "val_acc": vl_acc, "time_sec": dt})
        print(f"  ep{ep:02d}  train_loss={tr_loss:.3f}  val_loss={vl_loss:.3f}  val_acc={vl_acc:.3f}  ({dt:.1f}s)")

    # Фаза 2 — fine-tune всё с косинусным расписанием ------------------------
    for p_ in backbone_params:
        p_.requires_grad = True
    optimizer = optim.AdamW([
        {"params": backbone_params, "lr": args.lr_backbone},
        {"params": head_params, "lr": args.lr_head},
    ], weight_decay=args.weight_decay)
    n_full = args.epochs - args.head_epochs
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_full)

    print(f"\n[Phase 2] Fine-tuning full network for {n_full} epochs "
          f"(cosine LR, mixup α={args.mixup_alpha}, early-stop patience={args.patience})...")
    best_val_acc, best_epoch, no_improve = 0.0, 0, 0
    for ep in range(1, n_full + 1):
        t0 = time.time()
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, optimizer, device,
                                    scaler, train=True, mixup_alpha=args.mixup_alpha)
        vl_loss, vl_acc = run_epoch(model, val_loader, criterion, optimizer, device, scaler, train=False)
        scheduler.step()
        dt = time.time() - t0
        is_best = vl_acc > best_val_acc
        if is_best:
            best_val_acc, best_epoch, no_improve = vl_acc, ep, 0
            torch.save(model.state_dict(),
                       out_dir / f"{args.arch}_styles.pth")  # каноничное имя для деплоя
        else:
            no_improve += 1
        metrics.append({"phase": 2, "epoch": ep, "train_loss": tr_loss, "train_acc": tr_acc,
                        "val_loss": vl_loss, "val_acc": vl_acc, "time_sec": dt,
                        "lr": scheduler.get_last_lr()[0]})
        marker = " ⭐" if is_best else ""
        print(f"  ep{ep:02d}  train_loss={tr_loss:.3f}  val_loss={vl_loss:.3f}  val_acc={vl_acc:.3f}{marker}  ({dt:.1f}s)")
        if no_improve >= args.patience:
            print(f"  ⏹  Early stopping: val_acc не растёт {args.patience} эпох подряд.")
            break

    print(f"\nBest val accuracy: {best_val_acc:.4f} at phase-2 epoch {best_epoch}")

    # Финальный отчёт на validation set --------------------------------------
    print("\nLoading best checkpoint and producing per-class report...")
    model.load_state_dict(torch.load(out_dir / f"{args.arch}_styles.pth", map_location=device))
    evaluate_full(model, val_loader, device, class_names, out_dir)

    (out_dir / "metrics.json").write_text(json.dumps({
        "arch": args.arch,
        "best_val_acc": best_val_acc,
        "best_epoch_phase2": best_epoch,
        "class_names": class_names,
        "class_to_idx": train_ds.class_to_idx,
        "train_counts": {cls: counts[idx] for cls, idx in train_ds.class_to_idx.items()},
        "epochs": metrics,
    }, indent=2, ensure_ascii=False))

    print(f"\nArtifacts saved to {out_dir.resolve()}:")
    print(f"  - {args.arch}_styles.pth        ← положить в ml-service/weights/")
    print(f"  - metrics.json                  ← метрики по эпохам (для графиков)")
    print(f"  - classification_report.txt     ← per-class precision/recall/F1")
    print(f"  - confusion_matrix.csv / .png   ← кто с кем путается")
    print(f"  - class_to_idx.json             ← порядок классов (КРИТИЧНО для деплоя)")


if __name__ == "__main__":
    main()
