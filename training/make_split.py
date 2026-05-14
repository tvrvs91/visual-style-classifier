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
    │   │   ├── img001.jpg   (симлинк или копия)
    │   │   └── ...
    │   └── ...
    └── val/
        ├── airy/
        └── ...

Скрипт поддерживает воспроизведение pipeline'а, которым обучалась v3:
  1) MD5-дедупликация внутри каждого класса.
  2) Балансировка: cap до --target-count на класс (случайно с тем же seed).
  3) Дополнительный cap по конкретному классу через --cap-class name:N.
  4) Stratified split с фиксированным seed.

Файлы по умолчанию **не копируются** — создаются symlink'и (быстро, не
расходует диск). Drive остаётся нетронутым: если src=/content/drive/MyDrive/dataset
и dst=/content/dataset — на Drive ничего не меняется.

Воспроизведение v3 split'а (как было в Colab при обучении):

  python training/make_split.py \\
      --src /content/drive/MyDrive/dataset \\
      --dst /content/dataset \\
      --val-ratio 0.20 \\
      --seed 42 \\
      --dedup \\
      --target-count 600 \\
      --cap-class minimalist:500

Запуск дважды безопасен — старый dst стирается перед созданием нового.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import shutil
from pathlib import Path


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def dedup_files(files: list[Path]) -> tuple[list[Path], int]:
    """Удаляет дубликаты по MD5 содержимого, сохраняет первый встретившийся."""
    seen: dict[str, Path] = {}
    out: list[Path] = []
    duplicates = 0
    for f in files:
        try:
            h = md5_of(f)
        except OSError:
            continue
        if h in seen:
            duplicates += 1
        else:
            seen[h] = f
            out.append(f)
    return out, duplicates


def parse_cap_class(items: list[str]) -> dict[str, int]:
    """`--cap-class minimalist:500 dark:300` → {minimalist: 500, dark: 300}."""
    out: dict[str, int] = {}
    for item in items:
        if ":" not in item:
            raise SystemExit(f"--cap-class expects name:N, got {item!r}")
        name, n = item.split(":", 1)
        out[name] = int(n)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, type=Path,
                   help="Плоская структура: src/<class>/<image>")
    p.add_argument("--dst", required=True, type=Path,
                   help="Куда положить train/val структуру")
    p.add_argument("--val-ratio", type=float, default=0.2,
                   help="Доля val (default 0.2 = 80/20 как в v3 pipeline)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--copy", action="store_true",
                   help="Копировать вместо симлинков (для Windows без admin прав)")
    p.add_argument("--dedup", action="store_true",
                   help="MD5-дедупликация внутри каждого класса перед split'ом")
    p.add_argument("--target-count", type=int, default=None,
                   help="Cap каждого класса до N фото (random subsample). "
                        "Применяется после dedup.")
    p.add_argument("--cap-class", nargs="*", default=[],
                   help="Доп. cap для конкретных классов, формат name:N. "
                        "Приоритетнее --target-count для указанных классов.")
    args = p.parse_args()

    if not args.src.is_dir():
        raise SystemExit(f"src not a directory: {args.src}")

    rng = random.Random(args.seed)
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    cap_class = parse_cap_class(args.cap_class)

    classes = sorted(d.name for d in args.src.iterdir() if d.is_dir())
    if not classes:
        raise SystemExit(f"no class subdirectories in {args.src}")
    print(f"Classes ({len(classes)}): {classes}")

    if args.dst.exists():
        print(f"Removing existing {args.dst} ...")
        shutil.rmtree(args.dst)

    totals = {"train": 0, "val": 0}
    per_class_stats = []
    total_dups = 0
    for cls in classes:
        files = sorted(p for p in (args.src / cls).iterdir()
                       if p.suffix.lower() in exts)
        n_raw = len(files)

        # Шаг 1: dedup
        n_after_dedup = n_raw
        if args.dedup:
            files, dups = dedup_files(files)
            total_dups += dups
            n_after_dedup = len(files)

        # Шаг 2: random shuffle (детерминирован seed'ом)
        rng.shuffle(files)

        # Шаг 3: cap
        cap = cap_class.get(cls, args.target_count)
        n_after_cap = len(files)
        if cap is not None and len(files) > cap:
            files = files[:cap]
            n_after_cap = len(files)

        # Шаг 4: stratified split внутри класса
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
                        print(f"  symlink failed ({e}); falling back to copy")
                        shutil.copy2(src_abs, link)
            totals[split] += len(paths)
        per_class_stats.append((cls, n_raw, n_after_dedup, n_after_cap,
                                 len(splits["train"]), len(splits["val"])))

    if args.dedup:
        print(f"\n  MD5-дубликатов удалено: {total_dups}")

    print(f"\n{'Class':<14} {'Raw':>6} {'Dedup':>6} {'Cap':>6} {'Train':>6} {'Val':>6}")
    print("-" * 50)
    for cls, n_raw, n_dedup, n_cap, n_tr, n_va in per_class_stats:
        print(f"{cls:<14} {n_raw:>6} {n_dedup:>6} {n_cap:>6} {n_tr:>6} {n_va:>6}")
    print("-" * 50)
    print(f"{'TOTAL':<14} {'':>6} {'':>6} {'':>6} {totals['train']:>6} {totals['val']:>6}")
    print(f"\nSplit created in {args.dst.resolve()}")
    print(f"  → передавайте этот путь как --data-dir в E1–E6 скрипты")


if __name__ == "__main__":
    main()
