# ML-эксперименты E1–E6 (v3+ deep dive)

Шесть экспериментов поверх обученной v3-модели (`efficientnet_b0_styles.pth`).
Их назначение — углубить ML-часть дипломной работы (интерпретируемость,
качество представлений, калибровка, сравнение с foundation-model, переход
на multi-label).

Детали и план внесения в дипломный отчёт — в [`../docs/ml-experiments-log.md`](../docs/ml-experiments-log.md).

---

## Установка зависимостей

```bash
pip install -r training/requirements-experiments.txt
```

Это поверх существующих `torch`, `torchvision`, `scikit-learn`, `pillow`,
`matplotlib`. Дополнительно нужны: `scipy` (ANOVA в E3), `umap-learn`
(опционально в E2), `open_clip_torch` (E5).

---

## Обязательные входные артефакты

| Артефакт | Где взять |
|---|---|
| `efficientnet_b0_styles.pth` | Из обучения v3 (см. `train.py`) |
| `dataset/train/<class>/...`, `dataset/val/<class>/...` | Тот же датасет, что использовался для обучения v3 |

Если работаешь в Colab — смонтируй Drive и поставь оба элемента под
`/content/drive/MyDrive/diploma/`.

---

## E1 — Grad-CAM визуализация attention

**Цель.** Показать, на какие области изображения смотрит модель. Сильный
довод для §5 «Интерпретируемость» — убрать чёрный ящик.

```bash
python training/gradcam_viz.py \
    --weights ./out/efficientnet_b0_styles.pth \
    --data-dir ./dataset \
    --out-dir ./out/gradcam \
    --per-class 6 --errors 10
```

**Артефакты:**
- `out/gradcam/gradcam_{class}.png` — по каждому классу
- `out/gradcam/gradcam_grid.png` — общий 8×6 grid
- `out/gradcam/gradcam_errors.png` — топ-10 уверенно неправильных
- `out/gradcam/notes.json` — метаданные

**Время.** CPU ≈ 5–10 мин на полный прогон. GPU ≈ 30 сек.

---

## E2 — t-SNE / UMAP embedding visualization

**Цель.** Доказать, что 1280-мерные эмбеддинги — это правда «стиль»:
кластеры классов разделимы в 2D-проекции.

```bash
python training/embed_viz.py \
    --weights ./out/efficientnet_b0_styles.pth \
    --data-dir ./dataset \
    --out-dir ./out/embed \
    --split val \
    --umap
```

**Артефакты:**
- `out/embed/tsne.png`, `out/embed/umap.png`
- `out/embed/metrics.json` — silhouette, Davies-Bouldin, kNN5-accuracy
- `out/embed/centroid_similarity.csv/.png` — насколько классы близки
  в embedding space

**Время.** ~3 мин на CPU, ~30 сек на GPU.

**Что искать в результатах:**
- silhouette > 0.3 → представления хорошо разделимы;
- kNN5-acc близко к точности классификатора → представления, а не голова,
  делают основную работу;
- `monochrome` ↔ `vintage`/`minimalist` высокая centroid similarity → это
  причина F1=0.52 у monochrome.

---

## E3 — Score-card per-class signature

**Цель.** Формально определить классы через измеримые величины
(brightness, contrast, saturation, warmth, sharpness). Baseline-точность
на этих 5 признаках — нижняя планка для оправдания использования CNN.

```bash
python training/score_card_class.py \
    --data-dir ./dataset \
    --out-dir ./out/scorecard \
    --splits train val
```

**Артефакты:**
- `out/scorecard/radar.png` — 8 радарных чартов
- `out/scorecard/violins.png` — распределения по классам
- `out/scorecard/stats.csv` — mean/std/median per class
- `out/scorecard/anova.json` — статистическая значимость каждой метрики
- `out/scorecard/baseline.json` — logreg + RF на 5 фичах

**Время.** ~2 мин на 5 000 изображений (только CPU, нет нейросети).

**Что искать:**
- ANOVA p < 0.001 на 3–5 метриках → классы реально различимы по
  «дешёвым» признакам;
- logreg accuracy ~ 35–45% (если ~12.5% — это случайный baseline) → CNN
  даёт +30–35 пп поверх измеримых признаков, что оправдывает её
  использование.

---

## E4 — Probability calibration (temperature scaling)

**Цель.** Сделать confidence-числа осмысленными: P=0.7 должно означать
70% точность на бакете confidence ~ 0.7.

```bash
python training/calibration.py \
    --weights ./out/efficientnet_b0_styles.pth \
    --data-dir ./dataset \
    --out-dir ./out/calibration \
    --vector-scaling
```

**Артефакты:**
- `out/calibration/reliability_before.png` / `_after.png` / `_combined.png`
- `out/calibration/metrics.json` — ECE/MCE/Brier/NLL до и после
- `out/calibration/temperature.txt` — найденное T (1 число)

**Время.** ~3 мин на CPU.

**Что искать:**
- T > 1 → модель переуверена (типичный кейс с CrossEntropy + label smoothing);
- ECE падает в 2–5 раз → внести T в `ml-service/app/classifier.py`
  (делить logits на T перед softmax).

**Деплой:** если калибровка даёт значимый выигрыш, добавить в `classifier.py`:
```python
TEMPERATURE = float(open(WEIGHTS_DIR / "temperature.txt").read().strip())
logits = self.model.classifier(pooled_flat) / TEMPERATURE
```

---

## E5 — CLIP linear-probe и zero-shot

**Цель.** Сравнить с современной foundation model (CLIP ViT-B/32).
Linear probe (logreg поверх замороженного CLIP) и zero-shot
(text prompts) — два режима без переобучения CLIP.

```bash
pip install open_clip_torch
python training/clip_probe.py \
    --data-dir ./dataset \
    --out-dir ./out/clip \
    --model ViT-B-32 --pretrained openai
```

**Артефакты:**
- `out/clip/linear_probe_metrics.json` (full per-class)
- `out/clip/zero_shot_metrics.json`
- `out/clip/confusion_matrix_lp.png` / `_zs.png`
- `out/clip/comparison_table.csv` — сводка для отчёта
- `out/clip/tsne_clip.png` — CLIP embeddings в 2D

**Время.** ~5 мин на CPU, ~1 мин на GPU.

**Что искать:**
- linear probe accuracy: больше или меньше 0.726 (нашего baseline)?
- zero-shot accuracy: показывает, насколько CLIP «понимает» наши классы
  без обучения. Ожидаемо лучше работают `golden_hour`, `neon` (близкие
  к естественной лексике), хуже — `airy`, `minimalist` (визуально
  абстрактные).

---

## E6 — Multi-label fine-tune

**Цель.** Снять методологическое ограничение single-label. Одно фото
может одновременно быть `monochrome` + `minimalist`.

```bash
python training/train_multilabel.py \
    --data-dir ./dataset \
    --out-dir ./out/multilabel \
    --init-weights ./out/efficientnet_b0_styles.pth \
    --epochs 25 --head-epochs 5
```

**Артефакты:**
- `out/multilabel/efficientnet_b0_multilabel.pth` — новые веса
- `out/multilabel/thresholds.json` — per-class threshold
- `out/multilabel/metrics.json` — mAP, per-class F1, exact-match, Hamming
- `out/multilabel/co_label_stats.json` — статистика сгенерированных меток

**Время.** ~30 мин на T4 GPU. На CPU — несколько часов, не рекомендуется.

**Метки.** Автоматически расширены через score-card правила (см.
`derive_co_labels` в коде). Например, фото с saturation < 0.1
получает дополнительную метку `monochrome` поверх своей gold-метки.

**Что искать:**
- mAP на multi-label не сравнимо с single-label accuracy напрямую.
- Главное — F1 на «проблемных» классах (`monochrome`) должен подняться
  с 0.52 (single) до ~0.65+ (multi).
- exact_match_accuracy и Hamming accuracy — стандартные multi-label
  метрики для отчёта.

**Деплой:** опционально. Если результаты хорошие — переделать
`ml-service/app/classifier.py`:
- `torch.softmax` → `torch.sigmoid`
- top-3 по probabilities → все классы с `prob > threshold[class]`
- сохранить `thresholds.json` рядом с весами

---

## Порядок прогона

Рекомендую такой:

1. **E3 (score-card)** — самый быстрый, не требует весов. Получишь
   формальные определения классов сразу.
2. **E1 (Grad-CAM)** — быстро, показывает что модель делает.
3. **E2 (t-SNE)** — быстро, доказывает что представления — стиль.
4. **E4 (calibration)** — быстро, фикс под деплой.
5. **E5 (CLIP)** — средне, требует докачки модели (~350 MB).
6. **E6 (multi-label)** — долгий, требует GPU, опционально.

Первые 5 экспериментов — день-два спокойной работы; E6 — отдельный сеанс
с T4.

---

## Сборка результатов в дипломный отчёт

После каждого эксперимента:
1. Скопировать `out/<exp>/*.png` в `docs/figures/`.
2. В `docs/ml-experiments-log.md` отметить «выполнено» в чек-листе
   соответствующего раздела.
3. По итогам всех экспериментов — на основе пометок журнала
   переписать главы §1.2, §1.3, §4, §5, §6 в `docs/REPORT.md`.
