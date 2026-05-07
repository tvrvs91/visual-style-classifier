"""
Проверка датасета ДО обучения.

Что ловит:
- Дисбаланс классов (отношение max/min > 2 — флаг)
- Слишком маленькие классы (< 100 фото — флаг)
- Битые / нечитаемые файлы
- Подозрительно одинаковые файлы (одинаковый размер в байтах)
- Отношение train/val (должно быть ~ 4:1 / 5:1)

Использование:
  python dataset_check.py --data-dir ./dataset
"""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def scan_split(split_dir: Path) -> dict:
    """Возвращает {class: [paths]}."""
    if not split_dir.is_dir():
        return {}
    out = {}
    for cls_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
        files = [p for p in cls_dir.iterdir() if p.suffix.lower() in EXTS]
        out[cls_dir.name] = files
    return out


def check_files(files: list[Path]) -> tuple[list[Path], list[Path], dict]:
    """Возвращает (broken, dupes, size_groups)."""
    broken = []
    sizes = defaultdict(list)
    for p in files:
        try:
            with Image.open(p) as im:
                im.verify()
            sizes[p.stat().st_size].append(p)
        except (UnidentifiedImageError, OSError, Exception):
            broken.append(p)
    dupes = [paths for paths in sizes.values() if len(paths) > 1]
    return broken, dupes, sizes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--check-content-hash", action="store_true",
                    help="Дополнительно сверять MD5 файлов одинакового размера (медленно)")
    args = ap.parse_args()

    root = Path(args.data_dir)
    train = scan_split(root / "train")
    val = scan_split(root / "val")

    if not train:
        print(f"❌ Не найден {root}/train с подпапками классов.")
        return
    if not val:
        print(f"⚠  Не найден {root}/val — обучение возможно, но без честной валидации.")

    classes = sorted(set(train) | set(val))
    print(f"\nКлассы ({len(classes)}): {classes}")
    print(f"class_to_idx (алфавитный): {{{', '.join(f\"{c!r}: {i}\" for i, c in enumerate(classes))}}}")

    print("\n=== Распределение по классам ===")
    print(f"{'class':<14} {'train':>7} {'val':>7} {'tot':>7}  {'tr/val':>8}")
    train_counts, val_counts = {}, {}
    for c in classes:
        tr = len(train.get(c, []))
        vl = len(val.get(c, []))
        train_counts[c], val_counts[c] = tr, vl
        ratio = f"{tr/vl:.1f}" if vl else "-"
        print(f"{c:<14} {tr:>7} {vl:>7} {tr+vl:>7}  {ratio:>8}")

    total_train = sum(train_counts.values())
    total_val = sum(val_counts.values())
    print(f"\nИтого: train={total_train}, val={total_val}, ratio={total_train/max(total_val,1):.1f}:1")

    # Анализ дисбаланса
    print("\n=== Балансировка ===")
    if train_counts:
        mx, mn = max(train_counts.values()), min(train_counts.values())
        ratio = mx / max(mn, 1)
        print(f"max class size: {mx}  ({max(train_counts, key=train_counts.get)})")
        print(f"min class size: {mn}  ({min(train_counts, key=train_counts.get)})")
        print(f"max/min ratio:  {ratio:.2f}")
        if ratio > 2.0:
            print(f"❌ Сильный дисбаланс (>2x). WeightedRandomSampler в train.py поможет, но лучше добавить данных в маленькие классы.")
        elif ratio > 1.5:
            print(f"⚠  Лёгкий дисбаланс (1.5-2x). WeightedRandomSampler справится.")
        else:
            print(f"✓ Баланс ок (≤1.5x).")

    # Слишком мелкие классы
    weak = [c for c, n in train_counts.items() if n < 100]
    if weak:
        print(f"\n❌ Классы с <100 фото в трейне: {weak}")
        print(f"   На таком объёме модель не научится распознавать их надёжно.")
        print(f"   Цель: минимум 200, лучше 300+.")
    elif any(n < 200 for n in train_counts.values()):
        weak2 = [c for c, n in train_counts.items() if n < 200]
        print(f"\n⚠  Классы с <200 фото в трейне: {weak2} — желательно дополнить.")

    # Целостность файлов
    print("\n=== Целостность файлов ===")
    all_broken = 0
    all_dupes = 0
    for split_name, split in [("train", train), ("val", val)]:
        for cls, files in split.items():
            broken, dupes, _ = check_files(files)
            if broken:
                print(f"❌ {split_name}/{cls}: битых файлов {len(broken)}")
                for p in broken[:3]:
                    print(f"     {p}")
                if len(broken) > 3:
                    print(f"     ... и ещё {len(broken)-3}")
                all_broken += len(broken)
            if dupes:
                dup_count = sum(len(g) - 1 for g in dupes)
                print(f"⚠  {split_name}/{cls}: групп подозрительно одинаковых файлов {len(dupes)} ({dup_count} лишних)")
                if args.check_content_hash:
                    real_dupes = 0
                    for group in dupes:
                        hashes = defaultdict(list)
                        for p in group:
                            with open(p, "rb") as f:
                                hashes[hashlib.md5(f.read()).hexdigest()].append(p)
                        for h, g in hashes.items():
                            if len(g) > 1:
                                real_dupes += len(g) - 1
                    print(f"   подтверждённых MD5-дубликатов: {real_dupes}")
                all_dupes += dup_count
    if not all_broken and not all_dupes:
        print("✓ Битых файлов и дубликатов по размеру нет.")

    print("\n=== Итог ===")
    issues = []
    if total_train < 1000:
        issues.append(f"маленький трейн ({total_train} фото на {len(classes)} классов)")
    if any(n < 200 for n in train_counts.values()):
        issues.append("есть маленькие классы")
    mx_mn = max(train_counts.values()) / max(min(train_counts.values()), 1)
    if mx_mn > 2.0:
        issues.append(f"сильный дисбаланс ({mx_mn:.1f}x)")
    if all_broken:
        issues.append(f"битые файлы ({all_broken})")

    if issues:
        print("⚠  Перед обучением рекомендуется починить:")
        for i in issues:
            print(f"   - {i}")
    else:
        print("✓ Датасет выглядит здоровым. Можно обучать.")


if __name__ == "__main__":
    main()
