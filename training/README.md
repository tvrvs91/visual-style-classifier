# Training pipeline

Скрипты для подготовки данных, диагностики и переобучения модели визуальной
стилевой классификации.

📋 **Перед чтением кода:** [`ANALYSIS.md`](ANALYSIS.md) — там разбор того, что
не так с текущей моделью и в каком порядке чинить. Не пропускай — сэкономит
часы возни.

---

## Файлы

| Файл | Назначение | Когда запускать |
|---|---|---|
| `dataset_check.py` | Проверка датасета (баланс, битые файлы, размер) | **До** обучения |
| `train.py` | Улучшенный fine-tuning EfficientNet-B0 / ResNet-50 | Само обучение |
| `diagnose.py` | Confusion matrix + per-class метрики на validation set | **После** обучения |
| `ANALYSIS.md` | Диагноз текущих проблем + приоритеты фиксов | Прочитать первым |

---

## Структура датасета

Скрипты ожидают такую раскладку папок:

```
dataset/
├── train/
│   ├── airy/
│   │   ├── img001.jpg
│   │   └── img002.jpg
│   ├── dark/
│   ├── dramatic/
│   ├── golden_hour/
│   ├── minimalist/
│   ├── moody/
│   ├── street/
│   └── vintage/
└── val/
    ├── airy/
    └── ... (те же классы)
```

Имена папок = имена классов. PyTorch `ImageFolder` присваивает индексы
**в алфавитном порядке** — это важно для совпадения с порядком в
`ml-service/app/config.py:styles`.

---

## Полный цикл: от датасета до деплоя

### 0. Установка зависимостей (Colab — пропустить, всё уже есть)

```bash
pip install torch torchvision scikit-learn pillow matplotlib
```

### 1. Проверить датасет

```bash
python training/dataset_check.py --data-dir /path/to/dataset
```

Что увидишь:
- сколько фото в каждом классе train/val
- предупреждения про дисбаланс (>2x), маленькие классы (<200 фото)
- битые файлы и подозрительные дубликаты

**Если есть красные флаги — сначала чинить, потом обучать.**

### 2. Обучить модель

Базовый запуск (EfficientNet-B0, 25 эпох, всё хорошее включено):

```bash
python training/train.py \
    --data-dir /path/to/dataset \
    --epochs 25
```

С опциями:

```bash
python training/train.py \
    --data-dir /path/to/dataset \
    --arch efficientnet_b0 \      # или resnet50
    --epochs 30 \
    --head-epochs 5 \             # фаза 1: только голова
    --batch-size 32 \
    --lr-head 1e-3 \
    --lr-backbone 1e-4 \
    --label-smoothing 0.1 \
    --mixup-alpha 0.0 \           # 0.2-0.4 если есть переобучение
    --patience 7 \                # early stopping
    --out-dir ./out
```

**Что делает скрипт сам:**
1. Читает датасет, печатает class_to_idx и распределение
2. Создаёт `WeightedRandomSampler` — каждый класс получает равный вес в минибатче
3. **Фаза 1** (5 эпох): backbone заморожен, обучается только голова с lr=1e-3
4. **Фаза 2** (20 эпох): всё разморожено, backbone lr=1e-4, голова lr=1e-3, cosine annealing
5. Label smoothing 0.1, mixed precision на GPU
6. Early stopping если val_acc не растёт 7 эпох
7. Сохраняет лучший чекпоинт + полный отчёт

**Артефакты в `out/`:**

| Файл | Что там |
|---|---|
| `efficientnet_b0_styles.pth` | Веса лучшей эпохи — для деплоя |
| `metrics.json` | Поэпохные метрики — для графиков |
| `class_to_idx.json` | Маппинг классов — критично для деплоя |
| `classification_report.txt` | Per-class precision/recall/F1 |
| `confusion_matrix.csv` / `.png` | Кто с кем путается |

### 3. Диагностика обученной модели

```bash
python training/diagnose.py \
    --weights ./out/efficientnet_b0_styles.pth \
    --val-dir /path/to/dataset/val \
    --arch efficientnet_b0
```

Получишь:
- Per-class precision / recall / F1
- **Распределение топ-1 предсказаний** — сразу видно bias на доминирующий класс
- Топ-10 путаниц («модель сказала X, на самом деле Y»)
- Confusion matrix (counts + row-normalized)
- Confidence-gap между правильными и неправильными предсказаниями

### 4. Деплой в ML-сервис

```bash
# 1. Скопировать веса (имя должно совпадать с настроенным путём)
cp ./out/efficientnet_b0_styles.pth \
   /path/to/photo-style-classifier/ml-service/weights/

# 2. Перезапустить контейнер (rebuild не нужен — веса монтируются как volume)
cd /path/to/photo-style-classifier
docker compose restart ml-service

# 3. Проверить что подхватилось
curl http://localhost:8000/health
# должно быть: "model": "efficientnet_b0", "weights_path": "...styles.pth"
```

**Если поменял список классов** — также:
- Обновить `ml-service/app/config.py:styles` (алфавитный порядок!)
- Создать миграцию `backend/src/main/resources/db/migration/V2__update_styles.sql`
- `docker compose up -d --build` для backend

### 5. Опционально — включить TTA на инференсе

Test-time augmentation усредняет softmax по N аугментациям одного кадра.
Стабильно даёт +1–2 пп точности ценой ~×N времени инференса.

В `docker-compose.yml` для `ml-service`:

```yaml
environment:
  USE_TTA: "true"
  TTA_PASSES: "4"
```

```bash
docker compose up -d ml-service
curl http://localhost:8000/health
# увидишь: "tta": true, "tta_passes": 4
```

---

## Типичные проблемы и решения

### «Все предсказания в один класс»
- `WeightedRandomSampler` уже включён → проверь распределение `class_to_idx`
  печатается при старте train.py
- Если один класс намного меньше — добавь данных, не полагайся только на sampler

### «Train acc 90%, val acc 70%»
- Переобучение. Поможет: больше аугментации (`--mixup-alpha 0.3`),
  ранняя остановка (уже есть), больше данных

### «Val acc стоит на 65% и не растёт»
- Capacity модели не хватает → попробуй `--arch resnet50`
- Или модель достигла потолка качества данных → улучшай датасет

### «val_loss растёт, val_acc стоит/падает»
- Переобучение. Early stopping должен спасти. Если нет —
  уменьши `--head-epochs`, увеличь `--label-smoothing` до 0.15

### «CUDA out of memory»
- `--batch-size 16` (или 8 для ResNet-50 на T4)

---

## Метрики из текущего проекта

См. [`docs/training-metrics.md`](../docs/training-metrics.md) — сырые данные
двух предыдущих экспериментов и сравнение архитектур.
