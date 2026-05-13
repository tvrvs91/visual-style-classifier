"""
Создаёт детерминированный stratified train/val split из плоской структуры
датасета вида:

    src/
    ├── airy/
    │   ├── img001.jpg
    │   └── ...
    ├── dark/
    └── ...

в структуру, которую ждут training-скрипты (E1–E6 и train.py):

    dst/
    ├── train/
    │   ├── airy/
    │   │   ├── img001.jpg   (симлинк на src)
    │   │   └── ...
    │   └── ...
    └── val/
        ├── airy/
        └── ...

Файлы НЕ копируются, создаются symlink'и — это занимает секунды и не
расходует диск. Drive остаётся нетронутым: если запустить в Colab
с `src=/content/drive/MyDrive/dataset` и `dst=/content/dataset` — на
Drive ничего не меняется, всё работает только локально в Colab.

Запуск (в Colab):
  python training/make_split.py \\
    --src /content/drive/MyDrive/dataset \\
    --dst /content/dataset \\
    --val-ratio 0.15 \\
    --seed 42

Запуск дважды безопасен — старый `dst` стирается перед созданием нового.
"""
from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, type=Path,
                   help="Плоская структура: src/<class>/<image>")
    p.add_argument("--dst", required=True, type=Path,
                   help="Куда положить train/val структуру (симлинки)")
    p.add_argument("--val-ratio", type=float, default=0.15)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--copy", action="store_true",
                   help="Копировать вместо симлинков (для Windows без admin прав)")
    args = p.parse_args()

    if not args.src.is_dir():
        raise SystemExit(f"src not a directory: {args.src}")

    rng = random.Random(args.seed)
    exts = {".jpg", ".jpeg", ".png", ".webp"}

    classes = sorted(d.name for d in args.src.iterdir() if d.is_dir())
    if not classes:
        raise SystemExit(f"no class subdirectories in {args.src}")
    print(f"Classes: {classes}")

    if args.dst.exists():
        print(f"Removing existing {args.dst} ...")
        shutil.rmtree(args.dst)

    totals = {"train": 0, "val": 0}
    per_class_stats = []
    for cls in classes:
        files = sorted(p for p in (args.src / cls).iterdir()
                       if p.suffix.lower() in exts)
        rng.shuffle(files)
        cut = int(len(files) * (1.0 - args.val_ratio))
        splits = {"train": files[:cut], "val": files[cut:]}

        for split, paths in splits.items():
            target_dir = args.dst / split / cls
            target_dir.mkdir(parents=True, exist_ok=True)
            for f in paths:
                link = target_dir / f.name
                src_abs = f.resolve()
                if args.copy:
                    shutil.copy2(src_abs, link)
                else:
                    try:
                        link.symlink_to(src_abs)
                    except OSError as e:
                        # Windows без прав на симлинк — fallback на копию
                        print(f"  symlink failed ({e}); falling back to copy")
                        shutil.copy2(src_abs, link)
            totals[split] += len(paths)
        per_class_stats.append((cls, len(splits["train"]), len(splits["val"])))

    print(f"\n{'Class':<14} {'Train':>6} {'Val':>6}")
    print("-" * 28)
    for cls, n_tr, n_va in per_class_stats:
        print(f"{cls:<14} {n_tr:>6} {n_va:>6}")
    print("-" * 28)
    print(f"{'TOTAL':<14} {totals['train']:>6} {totals['val']:>6}")
    print(f"\nSplit created in {args.dst.resolve()}")
    print(f"  → передавайте этот путь как --data-dir в E1–E6 скрипты")


if __name__ == "__main__":
    main()
