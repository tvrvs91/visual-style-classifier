# Журнал ML-экспериментов (v4+)

Рабочие пометки для каждого эксперимента. Формат — заметки, не академический
текст. После того как все эксперименты прогнаны и собраны артефакты, разделы
этого журнала перерабатываются в главы диплома (§4 Датасет и обучение,
§5 Тестирование и результаты, §6 Направления развития).

Точка отсчёта — модель **v3** (EfficientNet-B0, 8 классов:
`airy, dark, dramatic, golden_hour, minimalist, monochrome, neon, vintage`,
val acc = 0.726, macro F1 = 0.718). См. `docs/training-metrics.md`.

---

## E1. Grad-CAM: визуализация attention модели

### Гипотеза
Дообученная EfficientNet-B0 действительно «смотрит» на стилистически релевантные
области кадра, а не на shortcut-признаки (лица, объекты, текст). Конкретные
ожидания по классам:

| Класс | Куда должна смотреть модель |
|---|---|
| `golden_hour` | На зоны тёплых засветов: небо, блики, контурный свет |
| `neon` | На яркие насыщенные пятна (вывески, неоновые источники) |
| `monochrome` | Равномерно по всему кадру (определяющий признак — отсутствие цвета) |
| `airy` | На светлые области (небо, светлый фон) |
| `dark` | На тёмные области, тени |
| `dramatic` | На зоны высокого контраста, границы света/тени |
| `vintage` | На текстуру, зерно, общий тон |
| `minimalist` | На центральный объект + большие пустые области |

### Что делает скрипт
`training/gradcam_viz.py` — оборачивает обученную EfficientNet-B0 в
`pytorch-grad-cam`, вычисляет Grad-CAM на последнем свёрточном блоке
(`model.features[-1]`), накладывает heatmap на исходное изображение. Прогоняет
N случайных изображений каждого класса из validation set, сохраняет
картинки-коллажи `gradcam_{class}.png` + общий grid `gradcam_grid.png`.

Дополнительно — отдельный режим «misclassified»: топ-K самых уверенных
неправильных предсказаний → визуализация куда смотрела модель, когда
ошибалась. Это даёт case-study для §5.3.

### Артефакты
- `out/gradcam/gradcam_{class}.png` — по 6 примеров на класс, рядом с
  оригиналом и heatmap-overlay.
- `out/gradcam/gradcam_grid.png` — сводный 8×6 grid для одной страницы отчёта.
- `out/gradcam/gradcam_errors.png` — топ-10 «уверенно неправильных».
- `out/gradcam/notes.json` — для каждого изображения: true class, predicted,
  confidence, путь к heatmap-файлу.

### Что войдёт в отчёт
- **§5 (новая подглава 5.4 «Интерпретируемость модели»)**: 1–2 страницы.
  Сводный grid + по одной репрезентативной картинке на каждый из 4–5 классов
  с разбором куда смотрит модель. Подпись: «Модель идентифицирует
  golden_hour преимущественно по областям тёплых засветов в верхней части
  кадра, что согласуется с операциональным определением класса».
- **§5.3 (case study ошибок)**: 3–5 «уверенно-неправильных» примеров с
  разбором «модель смотрела на X (Grad-CAM), отсюда предсказала Y, хотя
  истинный класс Z».

### Ожидаемая длительность
Прогон на val_set (~900 изображений) — несколько минут на CPU, 30 сек на GPU.
Не требует переобучения.

### Статус
- [ ] Скрипт написан
- [ ] Запущен на v3-весах
- [ ] Артефакты собраны
- [ ] Раздел перенесён в REPORT.md

---

## E2. Visualization of embedding space (t-SNE + UMAP)

### Гипотеза
1280-мерные эмбеддинги, извлечённые из предпоследнего слоя fine-tuned
EfficientNet-B0, образуют **разделимые кластеры** в low-dim проекции —
это формальное доказательство, что embedding space выучил стиль, а не
содержание. Дополнительно: класс `monochrome` должен «пересекаться» с
`minimalist`/`vintage` (что объясняет его низкий F1=0.52).

### Метрики на embedding'ах
- **Silhouette score** — насколько каждая точка ближе к своему кластеру,
  чем к чужому (range [-1, 1], > 0.3 = хорошо разделимо).
- **Davies-Bouldin index** — соотношение внутрикластерной к межкластерной
  дисперсии (меньше — лучше).
- **k-NN classifier на сырых embedding'ах** — top-1 accuracy без обучения,
  только cosine similarity. Если k-NN даёт сопоставимую точность с
  обученной головой — представления хорошие.

### Что делает скрипт
`training/embed_viz.py`:
1. Прогоняет всю validation выборку через `model.features → avgpool → flatten`,
   собирает (N, 1280) матрицу embedding'ов + (N,) метки.
2. Считает silhouette, Davies-Bouldin, k-NN-acc.
3. Считает t-SNE (perplexity=30) и UMAP (n_neighbors=15) до 2D.
4. Рисует scatter-plot: точка = фото, цвет = класс, легенда сбоку.
5. Считает **inter-class confusion** на embedding'ах: для каждой пары
   классов — средняя cosine similarity между их центроидами. Это
   эквивалент «как близко классы в embedding space», ожидаемо коррелирует
   с confusion matrix классификатора.

### Артефакты
- `out/embed/tsne.png`, `out/embed/umap.png` — две версии визуализации.
- `out/embed/metrics.json` — silhouette / Davies-Bouldin / kNN-acc.
- `out/embed/centroid_similarity.csv` — матрица 8×8 cosine между центроидами.
- `out/embed/embeddings.npy` — сырые векторы (для воспроизводимости).

### Что войдёт в отчёт
- **§5 (новая подглава 5.5 «Качество embedding space»)**: t-SNE + UMAP
  картинки рядом, таблица метрик, обсуждение разделимости. 1 страница.
- **§5.2 (analysis of class confusion)**: centroid similarity matrix + cross-ref
  с confusion matrix классификатора → если корреляция высокая, это
  объясняет ошибки на уровне представлений (не классификатора).

### Ожидаемая длительность
Forward-pass + dim-reduction ~3–5 мин на CPU. Не требует переобучения.

### Статус
- [ ] Скрипт написан
- [ ] Запущен на v3-весах
- [ ] Артефакты собраны
- [ ] Раздел перенесён в REPORT.md

---

## E3. Score-card / per-class statistical signature

### Гипотеза
Каждый класс имеет **операциональную сигнатуру** в пространстве 5 метрик
score-card (brightness, contrast, saturation, warmth, sharpness). Эти
сигнатуры **формально определяют** классы — что важно как обоснование
выбора таксономии в §1.2 диплома.

Ожидания (априорно):
- `airy` — высокий brightness, низкий contrast, средняя saturation.
- `dark` — низкий brightness.
- `dramatic` — высокий contrast.
- `golden_hour` — высокий warmth, средняя saturation.
- `monochrome` — около-нулевая saturation.
- `neon` — высокая saturation + (контр-интуитивно) средний brightness.
- `vintage` — пониженная saturation, тёплый сдвиг.
- `minimalist` — низкий contrast, высокий brightness, маленькая sharpness.

### Что делает скрипт
`training/score_card_class.py`:
1. Прогоняет всю train+val выборку через `_compute_scores()` из
   `ml-service/app/classifier.py` (5 чисел в [0,1] на изображение).
2. Группирует по классу, считает mean/std/median.
3. Строит **radar chart** для каждого класса (5 осей) — наглядный визуал
   сигнатуры.
4. Строит **violin plots** по 5 метрикам, разбитые по классам — показывает
   распределение, а не только среднее.
5. Считает **ANOVA / Kruskal–Wallis** на каждой метрике: какие метрики
   статистически значимо разделяют классы.
6. Считает **classification baseline**: только score-card (5 фич) →
   логистическая регрессия → accuracy. Это нижняя планка, на сколько
   процентов «дешёвые» признаки уже решают задачу. Разница между
   логрег и нейросетью = вклад глубоких представлений.

### Артефакты
- `out/scorecard/radar.png` — 8 radar-чартов в grid'е.
- `out/scorecard/violins.png` — 5 violin-plot'ов (по метрикам).
- `out/scorecard/stats.csv` — таблица mean/std по классам.
- `out/scorecard/anova.json` — F-значения и p-value по метрикам.
- `out/scorecard/baseline.json` — accuracy / F1 логистической регрессии.

### Что войдёт в отчёт
- **§1.2 (формализация классов)**: таблица «класс ↔ диапазоны метрик»,
  обоснование «таксономия не выдумана, а измерима».
- **§5 (новая 5.6 «Baseline classification on hand-crafted features»)**:
  логрег на 5 фичах vs полная нейросеть. Если разница ~20+ пп —
  оправдывает использование глубокой модели, а не классических методов.
- **§4 (датасет)**: violin plots визуализируют распределение фич — это
  пригодится в обсуждении сбалансированности классов.

### Статус
- [ ] Скрипт написан
- [ ] Запущен на v3-весах
- [ ] Артефакты собраны
- [ ] Раздел перенесён в REPORT.md

---

## E4. Probability calibration (temperature scaling)

### Гипотеза
softmax-выход дообученной модели **переуверен** — типично для CNN с
cross-entropy loss. Temperature scaling выровняет confidence-числа к
эмпирической точности; это важно для UI, где confidence показывается
пользователю.

### Метрики калибровки
- **Expected Calibration Error (ECE)** — взвешенная разница между средней
  confidence и точностью по бакетам (стандартный binning 15 бакетов).
- **Maximum Calibration Error (MCE)** — максимальная разница по бакетам.
- **Brier score** — squared error между one-hot и predicted probabilities.
- **Negative Log-Likelihood (NLL)** — log-loss на val_set.
- **Reliability diagram** — bar plot accuracy vs confidence по бакетам.

### Что делает скрипт
`training/calibration.py`:
1. Прогоняет val_set, собирает logits.
2. Считает baseline ECE / NLL / Brier до калибровки.
3. Подбирает оптимальную температуру T через градиентный спуск по
   `NLL(softmax(logits / T), y)` на val_set (как в Guo et al. 2017).
4. Перерисовывает reliability diagram до и после, считает все метрики
   после.
5. Опционально: **vector scaling** (per-class temperature) — даёт лучше,
   но менее стабилен на маленьких val_set.

### Артефакты
- `out/calibration/reliability_before.png`, `..._after.png`.
- `out/calibration/metrics.json` — ECE/MCE/Brier/NLL до и после, найденная T.
- `out/calibration/temperature.txt` — само значение T для деплоя.

### Что войдёт в отчёт
- **§5 (новая 5.7 «Калибровка вероятностей»)**: reliability diagrams
  до/после, таблица метрик, найденное T. 0.5 страницы.
- Упомянуть в **§3.4** (frontend): «отображаемый процент confidence —
  это уже откалиброванный softmax с T = {T_value}, что эмпирически
  снижает ECE с {X} до {Y}».

### Развёртывание
Если калибровка показывает значимый выигрыш (ECE падает > 2×), внести в
`ml-service/app/classifier.py`: делить logits на T перед softmax. Сохранить
T рядом с весами как `temperature.txt`.

### Статус
- [ ] Скрипт написан
- [ ] Запущен на v3-весах
- [ ] Артефакты собраны
- [ ] T внесена в ml-service (если выигрыш есть)
- [ ] Раздел перенесён в REPORT.md

---

## E5. CLIP linear-probe — современная foundation model

### Гипотеза
CLIP ViT-B/32 обучен на 400M пар (изображение, текст) и его представления
**априорно ближе к стилистической семантике**, чем ImageNet-веса
EfficientNet-B0 (обученной на категориях объектов). Линейный probe (logreg
поверх замороженного CLIP) должен давать сопоставимую или лучшую точность,
чем full fine-tune EfficientNet-B0 — это убедительный аргумент про
foundation models в дипломе.

### Подвопросы
1. **Linear probe accuracy** на val_set: > или < 0.726 (наш baseline)?
2. **Размер представления** (512-dim у ViT-B/32 vs 1280-dim у B0) —
   достаточен ли?
3. **Zero-shot classification** через текстовые промпты («a {style} photo»)
   без обучения вообще — что покажет?
4. **Сравнительная стоимость**: размер модели CLIP (350 MB) vs B0 (16 MB).

### Что делает скрипт
`training/clip_probe.py`:
1. Грузит OpenAI CLIP ViT-B/32 (`openai/clip-vit-base-patch32` через
   transformers или `clip` пакет).
2. **Linear probe**: прогоняет train+val через image encoder, обучает
   sklearn LogisticRegression (C=1.0, max_iter=1000) на train embeddings,
   тестит на val.
3. **Zero-shot**: для каждого класса формирует текстовый prompt
   («a moody photo», «a golden hour photo», ...), кодирует CLIP text
   encoder, считает cosine similarity image embedding ↔ text embeddings,
   argmax = предсказание. Без обучения.
4. Сравнивает с EfficientNet-B0 fine-tune (наш baseline) по: accuracy,
   per-class F1, confusion matrix.
5. **Embedding space comparison**: silhouette / Davies-Bouldin на CLIP
   embeddings, сравнить с E2.

### Артефакты
- `out/clip/linear_probe_metrics.json` — accuracy, macro/weighted F1,
  per-class report.
- `out/clip/zero_shot_metrics.json` — то же для zero-shot.
- `out/clip/confusion_matrix.png` — для linear probe.
- `out/clip/comparison_table.csv` — сводка: B0_fine_tune / CLIP_linear_probe
  / CLIP_zero_shot по 4–5 метрикам.
- `out/clip/embeddings_tsne.png` — t-SNE CLIP embeddings (cf. E2).

### Что войдёт в отчёт
- **§1.3 (выбор архитектуры) — расширение**: добавить CLIP в таблицу
  сравнения архитектур.
- **§5 (новая 5.8 «Сравнение с foundation model»)**: ключевая таблица +
  обсуждение. 1–1.5 страницы. Главные выводы (после прогона):
  - linear probe CLIP vs full fine-tune B0 — кто кого
  - zero-shot CLIP без размеченных данных — какая «бесплатная» точность
  - какие классы CLIP различает лучше (вероятно `golden_hour`, `neon`
    как «текстовые» концепты) и какие хуже (вероятно `airy`/`minimalist`
    как визуально-абстрактные)
- **§6 (направления развития)**: «следующая итерация — fine-tune CLIP
  с LoRA для дальнейшего повышения качества».

### Зависимости
Добавить в training-окружение: `transformers`, `clip-by-openai` или
`open_clip_torch`. Это **не** идёт в production ml-service (там остаётся
B0 ради компактности).

### Статус
- [ ] Скрипт написан
- [ ] Linear probe прогнан
- [ ] Zero-shot прогнан
- [ ] Артефакты собраны
- [ ] Раздел перенесён в REPORT.md

---

## E6. Multi-label classification (концептуальный апгрейд)

### Гипотеза
Single-label CrossEntropy формально неправилен для задачи стиля: один кадр
**может одновременно** быть `monochrome` + `minimalist` + `dramatic`.
Переход на multi-label (sigmoid + BCE) должен:
1. Поднять F1 на «ортогональных» классах (`monochrome`).
2. Дать более калиброванные independent probabilities.
3. Соответствовать постановке задачи, заявленной в §1.1 REPORT.md
   («одной фотографии может соответствовать одновременно несколько стилей»).

### Подвопросы — стратегия меток
Multi-label требует multi-label меток, которых у нас сейчас нет (датасет
размечен single-label через `ImageFolder`). Три варианта получения:

**Вариант A — pseudo-labels от текущей модели.** Для каждого изображения:
- gold label = текущий folder-class (вес 1.0)
- co-labels = top-K softmax от v3-модели с confidence > threshold (вес
  0.5 если confidence > 0.3)

Плюс — нулевая стоимость разметки. Минус — обучение на собственных
предсказаниях усиливает существующие смещения.

**Вариант B — operationally-defined co-labels через score-card.**
- `monochrome` co-label если saturation < 0.1
- `warm` co-label если warmth > 0.6
- `high-contrast` if contrast > 0.7
- ...

Плюс — независимый от модели сигнал. Минус — score-card имеет 5 фич,
а классов 8 — нужна явная схема маппинга.

**Вариант C — manual re-labelling выборки (100–200 фото).**
- Самый качественный, но дорогой по времени.

**Решение для эксперимента:** **A + B комбинированно**. Gold-метки +
score-card-derived co-labels (вариант B как наименее смещённый), pseudo-labels
варианта A только как ablation для сравнения.

### Что делает скрипт
`training/train_multilabel.py`:
1. Расширяет `ImageFolder` кастомным датасетом, который генерирует
   multi-hot вектор меток по правилу:
   - gold-метка из папки — 1.0
   - score-card co-метки по жёстким правилам — 1.0
   - максимум 3 активных класса на изображение
2. Меняет head на `nn.Linear(1280, 8)` (как было) + loss `BCEWithLogitsLoss`
   с `pos_weight` (по подсчёту позитивов на класс).
3. Двухфазный fine-tune как в v3.
4. **Threshold tuning**: для каждого класса находим оптимальный
   threshold на val_set по F1 (или Youden's J).
5. Final metrics: per-class precision/recall/F1, **mAP** (mean average
   precision) — стандартная metric для multi-label, exact-match
   accuracy (строгая), Hamming accuracy (мягкая).

### Артефакты
- `out/multilabel/best.pth` — веса.
- `out/multilabel/thresholds.json` — per-class threshold.
- `out/multilabel/metrics.json` — mAP, per-class F1, exact-match, Hamming.
- `out/multilabel/comparison.csv` — single-label v3 vs multi-label v4.
- `out/multilabel/co_label_stats.json` — сколько изображений с >1 меткой,
  какие пары меток чаще встречаются.

### Что войдёт в отчёт
- **§1.1**: уже было заявлено multi-label, теперь это технически реализовано.
- **§4 (датасет)**: новый подраздел 4.7 «Дополнительная разметка через
  score-card-производные метки» — методология derivation.
- **§5 (новая 5.9 «Multi-label расширение»)**: сравнительная таблица
  v3 single-label vs v4 multi-label, обсуждение прироста на `monochrome`
  / `vintage`. 1.5–2 страницы.
- **§6**: «дальнейшее развитие — ручная разметка multi-label на 1000 фото
  для устранения зависимости от score-card heuristics».

### Зависимости
Это **переобучение**, нужен GPU (Colab T4 ~30 мин). В отличие от E1–E5,
этот эксперимент производит новые веса, которые можно или нельзя
вкатить в production (зависит от итогов).

### Статус
- [ ] Скрипт написан
- [ ] Co-label derivation отлажена
- [ ] Прогон на T4
- [ ] Артефакты собраны
- [ ] Решение: вкатывать ли в ml-service
- [ ] Раздел перенесён в REPORT.md

---

## Сводка ожидаемых артефактов

После полного прогона E1–E6 в репо появятся (через коммит / Git LFS,
если нужно — артефакты в `docs/figures/`, веса в `ml-service/weights/`):

```
docs/
└── figures/                       ← коммитим в репо
    ├── gradcam_grid.png
    ├── gradcam_errors.png
    ├── tsne_embeddings.png
    ├── umap_embeddings.png
    ├── scorecard_radar.png
    ├── scorecard_violins.png
    ├── reliability_before.png
    ├── reliability_after.png
    ├── clip_comparison.png
    └── multilabel_comparison.png

training/
└── out/                            ← gitignored, сырые данные
    ├── gradcam/
    ├── embed/
    ├── scorecard/
    ├── calibration/
    ├── clip/
    └── multilabel/
```

## План внесения в REPORT.md (после прогона)

| Эксперимент | Новый раздел в REPORT | Объём |
|---|---|---:|
| E1 Grad-CAM | §5.4 Интерпретируемость | 1–2 стр |
| E2 t-SNE/UMAP | §5.5 Качество embeddings | 1 стр |
| E3 Score-card | §1.2 (расширение) + §5.6 Baseline | 1.5 стр |
| E4 Calibration | §5.7 Калибровка | 0.5 стр |
| E5 CLIP | §1.3 (расширение) + §5.8 Foundation models | 1.5 стр |
| E6 Multi-label | §4.7 + §5.9 + §6 (развитие) | 2 стр |
| **Итого** | | **+7–9 стр** к ML-части |

После заполнения раздел «Глава 4. Датасет и обучение» и «Глава 5.
Тестирование и результаты» вырастают с текущих ~2–3 страниц до 12–15 —
это уже соразмерно дипломной работе по ML, а не приложению к
веб-разработке.
