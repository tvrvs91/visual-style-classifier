# Полный pipeline в Google Colab — копируй-вставляй

**Идея:** 4 ячейки. Копируешь по одной, запускаешь, ждёшь. Между ячейками ничего не меняй.

**Сначала** в Colab: `Runtime → Change runtime type → T4 GPU` (бесплатно). Без GPU обучение займёт ~12 часов вместо ~30 минут.

Создай новый ноутбук, назови его, например, **`train_pipeline.ipynb`**.

---

## Ячейка 1 — Setup: монтируем Drive и клонируем репо

```python
from google.colab import drive
drive.mount('/content/drive')

!rm -rf /content/visual-style-classifier
!git clone https://github.com/tvrvs91/visual-style-classifier.git /content/visual-style-classifier
%cd /content/visual-style-classifier

print("\n✓ Setup done")
```

---

## Ячейка 2 — Подготовка датасета (чистка + split)

```python
"""
Что делает эта ячейка:
1. Удаляет папку street (не визуальный стиль, а жанр)
2. Урезает moody до 500 фото (был дисбаланс 1432 vs 292)
3. Делает train/val split 80/20 в /content/dataset_split
   (локально на диск Colab — Drive слишком медленный для обучения)
"""
import os, random, shutil
from pathlib import Path

SRC = '/content/drive/MyDrive/dataset'
DST = '/content/dataset_split'
EXTS = {'.jpg', '.jpeg', '.png', '.webp'}
random.seed(42)

# 1. Удалить street целиком
street = Path(SRC) / 'street'
if street.exists():
    shutil.rmtree(street)
    print(f"✓ Удалён street/")
else:
    print(f"  street/ уже отсутствует")

# 2. Урезать moody до 500
moody = Path(SRC) / 'moody'
if moody.exists():
    files = [f for f in moody.iterdir() if f.suffix.lower() in EXTS]
    if len(files) > 500:
        random.shuffle(files)
        for f in files[500:]:
            f.unlink()
        print(f"✓ moody/ обрезан до 500 (было {len(files)})")
    else:
        print(f"  moody/ уже ≤500 фото ({len(files)})")

# 3. Распечатать текущее состояние
print("\n=== Состояние датасета ===")
total = 0
for cls in sorted(Path(SRC).iterdir()):
    if not cls.is_dir(): continue
    n = sum(1 for f in cls.iterdir() if f.suffix.lower() in EXTS)
    total += n
    print(f"  {cls.name:14s} {n:5d}")
print(f"  всего: {total}")

# 4. train/val split → /content/dataset_split
print("\n=== Создаём train/val split ===")
if Path(DST).exists():
    shutil.rmtree(DST)

for cls_dir in sorted(Path(SRC).iterdir()):
    if not cls_dir.is_dir(): continue
    files = [f for f in cls_dir.iterdir() if f.suffix.lower() in EXTS]
    random.shuffle(files)
    split_at = int(len(files) * 0.8)
    for split, lst in [('train', files[:split_at]), ('val', files[split_at:])]:
        out = Path(DST) / split / cls_dir.name
        out.mkdir(parents=True, exist_ok=True)
        for f in lst:
            shutil.copy2(f, out / f.name)
    print(f"  {cls_dir.name:14s} train={split_at:4d}  val={len(files)-split_at:4d}")

print(f"\n✓ Датасет готов: {DST}")
```

**Что должно быть на выходе:**
```
airy        train=396   val=99
dark        train=303   val=76
dramatic    train=233   val=59
golden_hour train=294   val=74
minimalist  train=435   val=109
moody       train=400   val=100
vintage     train=337   val=85
```

(числа примерные — зависит от твоего датасета)

> ⚠ **Заметил `moody` всё ещё в списке.** На этой итерации оставляем его сокращённым — посмотрим, как модель себя поведёт без street и с балансом. Если bias-эффект сохранится — следующим шагом уберём и его полностью. Но сейчас лишний прогон с/без — это полезные данные для отчёта.

---

## Ячейка 3 — Проверка датасета нашим скриптом

```python
!python training/dataset_check.py --data-dir /content/dataset_split
```

Должно быть зелёное «датасет выглядит здоровым». Если красное — скажи в чате, разберёмся.

---

## Ячейка 4 — Обучение + диагностика (главное, ~30-60 минут)

```python
"""
Обучает EfficientNet-B0 на нашем pipeline:
- двухфазный fine-tune (5 эпох голова, 25 эпох всё)
- WeightedRandomSampler балансирует классы в минибатчах
- cosine annealing LR
- early stopping если val_acc не растёт 7 эпох
- сохраняет лучший .pth + полный отчёт в Drive
"""
OUT = '/content/drive/MyDrive/training_out_v3'  # ← результаты сохранятся сюда в Drive
!mkdir -p "$OUT"

!python training/train.py \
    --data-dir /content/dataset_split \
    --out-dir "$OUT" \
    --arch efficientnet_b0 \
    --epochs 30 \
    --head-epochs 5 \
    --batch-size 32 \
    --label-smoothing 0.1 \
    --patience 7

# Диагностика на лучшем чекпоинте
print("\n\n=== ДИАГНОСТИКА ===\n")
!python training/diagnose.py \
    --weights "$OUT/efficientnet_b0_styles.pth" \
    --val-dir /content/dataset_split/val \
    --arch efficientnet_b0 \
    --out-dir "$OUT/diag"
```

**Что сохранится в `/content/drive/MyDrive/training_out_v3/`:**

| Файл | Что |
|---|---|
| `efficientnet_b0_styles.pth` | **Веса лучшей эпохи** — это вставлять в `ml-service/weights/` |
| `metrics.json` | поэпохные метрики для графиков |
| `class_to_idx.json` | порядок классов |
| `classification_report.txt` | per-class P/R/F1 |
| `confusion_matrix.{csv,png}` | кто с кем путается |
| `diag/` | расширенный диагностический отчёт |

---

## После того как обучение прошло

1. **Скачай `efficientnet_b0_styles.pth` локально**:
   ```python
   from google.colab import files
   files.download(f"{OUT}/efficientnet_b0_styles.pth")
   ```
   (или возьми руками из Drive)

2. **Положи в проект** на своей машине:
   ```
   C:\projects\photo-style-classifier\ml-service\weights\efficientnet_b0_styles.pth
   ```
   (заменить предыдущий файл)

3. **Перезапусти проект**:
   ```powershell
   cd C:\projects\photo-style-classifier
   git pull        # подтянет обновлённый config.py с 6 классами и миграцию
   docker compose up -d --build backend ml-service
   curl http://localhost:8000/health
   ```

   В `/health` должно быть `"styles": ["airy", "dark", "dramatic", "golden_hour", "minimalist", "vintage"]`
   (если на этой итерации оставили moody — он тоже там будет).

4. **Скажи мне когда готово** — посмотрим на metrics.json и diagnose-отчёт, обсудим что улучшать дальше.

---

## Если что-то пошло не так

| Симптом | Решение |
|---|---|
| `CUDA out of memory` | В ячейке 4 поменяй `--batch-size 32` → `--batch-size 16` |
| `FileNotFoundError /content/drive/...` | Drive отвалился, перезапусти ячейку 1 |
| Обучение слишком долгое | Убедись что в `Runtime → Change runtime type` стоит **T4 GPU** |
| `Permission denied` при скачивании | Дай Colab доступ к Drive в pop-up окне |
| Что-то ещё | Скинь весь вывод ячейки сюда, разберёмся |
