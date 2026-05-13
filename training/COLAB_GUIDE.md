# Colab — пошаговая инструкция для прогона E1–E6

## TL;DR — что нужно сделать

1. Положить в Drive файл `efficientnet_b0_styles.pth` (16 МБ, из локального `ml-service/weights/`).
2. Открыть в Colab **один** блокнот: [`training/colab_runbook.ipynb`](colab_runbook.ipynb) (см. ниже как).
3. Включить GPU (Runtime → Change runtime type → T4).
4. Запускать ячейки сверху вниз, **по одной**, ожидая завершения каждой.
5. После последней ячейки артефакты будут в `MyDrive/diploma_out/`.

Один блокнот на всё. Не нужно несколько.

---

## Структура Drive (что должно быть до начала)

```
MyDrive/
├── dataset/                              ← у тебя уже есть, плоская структура
│   ├── airy/
│   ├── dark/
│   ├── dramatic/
│   ├── golden_hour/
│   ├── minimalist/
│   ├── monochrome/
│   ├── neon/
│   └── vintage/
└── efficientnet_b0_styles.pth            ← положить вручную (drag&drop)
```

Файл весов находится у тебя локально по пути:
`C:\projects\photo-style-classifier\ml-service\weights\efficientnet_b0_styles.pth`

Перетащи его в корень `MyDrive` (или в `MyDrive/diploma/` — тогда поправь
переменную `WEIGHTS` в первой code-ячейке блокнота).

---

## Что появится в Drive после прогона

```
MyDrive/
├── dataset/                              (не трогается)
├── efficientnet_b0_styles.pth            (не трогается)
└── diploma_out/                          ← создастся скриптами
    ├── scorecard/    (E3: radar.png, violins.png, stats.csv, anova.json, baseline.json)
    ├── gradcam/      (E1: gradcam_grid.png, gradcam_errors.png, gradcam_<class>.png, notes.json)
    ├── embed/        (E2: tsne.png, umap.png, centroid_similarity.png/.csv, metrics.json, embeddings.npy)
    ├── calibration/  (E4: reliability_combined.png, metrics.json, temperature.txt)
    ├── clip/         (E5: comparison_table.csv, confusion_matrix_*.png, tsne_clip.png, *_metrics.json)
    └── multilabel/   (E6: efficientnet_b0_multilabel.pth, thresholds.json, metrics.json, co_label_stats.json)
```

---

## Как открыть блокнот в Colab

Три способа, по убыванию удобства:

**Способ 1 — прямая ссылка** (после `git push`):
```
https://colab.research.google.com/github/tvrvs91/visual-style-classifier/blob/claude/sleepy-gould-93f13f/training/colab_runbook.ipynb
```

**Способ 2 — через GitHub.com**:
GitHub → ветка `claude/sleepy-gould-93f13f` → `training/colab_runbook.ipynb` →
кнопка `Open in Colab` (если установил расширение) или скачать и
загрузить в `colab.research.google.com`.

**Способ 3 — File → Open notebook → GitHub** в Colab:
- репозиторий: `tvrvs91/visual-style-classifier`
- ветка: `claude/sleepy-gould-93f13f`
- путь: `training/colab_runbook.ipynb`

---

## Что делает каждая ячейка

### Ячейки setup (1–5)

| Ячейка | Что делает |
|---|---|
| 1 | Mount Drive (попросит авторизацию) |
| 2 | `git clone` нужной ветки |
| 3 | `pip install` доп. зависимостей (umap, scipy, open_clip) |
| 4 | Объявляет переменные `WEIGHTS`, `DATA`, `OUT` и проверяет наличие файлов |
| 5 | Запускает `make_split.py` — создаёт `/content/dataset/train` и `/val` через симлинки. **Drive не трогается.** |

### Эксперимент-ячейки (по 2 на каждый из E3, E1, E2, E4, E5, E6)

Для каждого эксперимента:
1. **Прогон скрипта** — пишет артефакты в `MyDrive/diploma_out/<exp>/`.
2. **Просмотр результатов** — показывает картинки прямо в Colab.

---

## Порядок и время

| # | Эксперимент | Нужен GPU? | Примерное время |
|---|---|---|---|
| 0 | Setup + split | нет | ~2 мин (зависит от скорости Drive) |
| E3 | Score-card | нет | ~5 мин |
| E1 | Grad-CAM | желательно | 5 CPU / 1 GPU |
| E2 | Embeddings | желательно | 5 CPU / 2 GPU |
| E4 | Калибровка | нет | 3 мин |
| E5 | CLIP | желательно | 20 CPU / 5 GPU |
| E6 | Multi-label | **обязательно** | ~30 мин T4 |

**Итого с GPU:** ~50–60 минут. Без GPU — около 2 часов (E6 не запускать).

**Не торопись** — запускай ячейку за ячейкой, смотри результаты. Если
что-то падает — пришли мне traceback, я починю.

---

## Минимальный путь (без E6)

Если не хочешь переобучать модель (E6 опционален):

1. Setup (ячейки 1–5).
2. E3, E1, E2, E4, E5 (10 ячеек × прогон + просмотр).
3. Артефакты в Drive — готовы для диплома.

E6 (multi-label) — это «вишенка на торте», экспериментальное направление.
Можно прогнать позже, отдельной сессией с T4.

---

## После прогона

Когда все нужные эксперименты пройдут:

1. Загрузи папку `MyDrive/diploma_out/` себе на локальный диск
   (правый клик → Download as zip).
2. Распакуй в worktree этой ветки в `docs/figures/`:
   ```
   docs/figures/
   ├── scorecard/
   ├── gradcam/
   ├── embed/
   └── ...
   ```
3. Скажи мне — я прочитаю результаты и переведу их в текст диплома
   (главы 4.7, 5.4–5.9, направления развития в §6).

Альтернатива — закоммить артефакты прямо из Colab:
```python
%cd /content/visual-style-classifier
!cp -r {OUT}/* docs/figures/
!git add docs/figures/
!git -c user.email='тут_твой_email' -c user.name='тут_твой_логин' commit -m 'add E1-E6 artifacts'
!git push
```
(тебе нужно будет ввести Personal Access Token при push).

---

## Если что-то падает

- **«нет файла весов»** — не положил `.pth` в Drive, или путь не такой.
  Проверь `!ls /content/drive/MyDrive/efficientnet_b0_styles.pth`.
- **«нет датасета»** — проверь имя папки (должна быть ровно `dataset`).
- **CUDA OOM в E6** — уменьши `--batch-size 16` или `--num-workers 0`.
- **«open_clip not found»** — пере-запусти ячейку 3 (`pip install`).
- **Drive отвалился** — пере-запусти ячейку 1, авторизуйся повторно.

Любая другая ошибка — присылай traceback, разберёмся.
