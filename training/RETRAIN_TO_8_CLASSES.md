# Переобучение под новую таксономию: 7 → 8 классов

**Замысел этой итерации:** убрать слабый класс `moody` (F1=0.55, путается с
dark/dramatic/vintage) и добавить два **визуально отчётливых** класса —
`monochrome` и `neon`. Они диаметрально различимы между собой и от
существующих классов по объективным метрикам (saturation, brightness, contrast).

## Новая таксономия (8 классов, алфавитный порядок)

| # | Класс | Признаки | Источник данных |
|---|---|---|---|
| 0 | `airy` | High-key, светлая палитра, низкий contrast | (уже есть) |
| 1 | `dark` | Low-key, преобладают тёмные тона | (уже есть) |
| 2 | `dramatic` | Высокий contrast, выраженная светотень | (уже есть) |
| 3 | `golden_hour` | Тёплая цветовая температура, sunset/sunrise | (уже есть) |
| 4 | `minimalist` | Negative space, простая композиция | (уже есть) |
| 5 | **`monochrome`** ✨ | Saturation ≈ 0, B&W, оттенки серого | **новый класс** |
| 6 | **`neon`** ✨ | Яркие синтетические цвета на тёмном фоне | **новый класс** |
| 7 | `vintage` | Faded warm low-saturation, плёночный look | (уже есть) |

**Удалено:** `moody` (как пересекающийся с другими атмосферными классами).

## Шаг 1 — обновить `01_dataset_collection.ipynb`

Открой в Drive `Colab Notebooks/01_dataset_collection.ipynb`. В переменной
`STYLES` **замени** `moody` на два новых класса:

```python
STYLES = {
    "minimalist": [
        "minimalist photography", "minimal clean photo", "negative space photo",
        "minimal architecture", "clean lines minimal", "white minimal interior",
        "minimal abstract photo"
    ],
    "golden_hour": [
        "golden hour photography", "sunset warm light", "magic hour photo",
        "golden light portrait", "backlit golden sunset", "silhouette sunset",
        "golden field sunset"
    ],
    "dark": [
        "dark photography", "low key photo", "noir dark",
        "shadow photography", "dark portrait low key", "candlelight dark",
        "dark moody still life"
    ],
    "airy": [
        "airy bright photography", "light airy photo", "dreamy light photo",
        "overexposed dreamy", "soft pastel photography", "bright window light",
        "hazy bright outdoor"
    ],
    "vintage": [
        "vintage film photography", "retro analog photo", "film grain",
        "faded retro photo", "lomography photo", "polaroid style",
        "analog grain portrait"
    ],
    "dramatic": [
        "dramatic photography", "high contrast dramatic", "cinematic photo",
        "stormy dramatic", "harsh shadow portrait", "cinematic widescreen",
        "dramatic sky landscape"
    ],

    # ↓↓↓ НОВЫЕ КЛАССЫ ↓↓↓
    "monochrome": [
        "black and white photography", "monochrome photo", "bw portrait",
        "black white street", "high contrast bw", "grayscale photography",
        "minimalist black white", "bw landscape"
    ],
    "neon": [
        "neon photography", "cyberpunk lights", "neon city night",
        "neon signs photography", "synthwave aesthetic", "tokyo neon",
        "purple pink neon", "vivid neon glow"
    ],
}
```

(`street` уже удалён, `moody` тоже не упоминается.)

Запусти ячейку — она скачает ~250-500 фото на каждый новый класс. Время:
~30-60 минут (зависит от Unsplash/Pexels rate limits).

## Шаг 2 — удалить старый `moody` из Drive

В drive.google.com открой `MyDrive/dataset/` и удали папку `moody/`
(перетащи в корзину). Подтверди что осталось 8 папок:

```
airy/  dark/  dramatic/  golden_hour/  minimalist/  monochrome/  neon/  vintage/
```

## Шаг 3 — переобучить через `train_pipeline.ipynb`

Открой `train_pipeline.ipynb` в Colab. Все 4 ячейки из `COLAB.md`
запускаются как раньше — `train.py` автоматически обнаружит 8 классов
по структуре папок (через `datasets.ImageFolder`).

**ВАЖНО:** В **ячейке 2** удали блок про обрезку `moody` — теперь его нет:

```python
# Заменить этот блок:
moody = Path(SRC) / 'moody'
if moody.exists():
    ...
# на этот (просто отчитать состояние):
print("✓ moody больше нет в датасете")
```

Также в той же ячейке для **подстраховки** удали `street/` если он
случайно вернулся, и добавь проверку что есть `monochrome` и `neon`.

Запусти все 4 ячейки. Ожидаемое время на T4:
- Ячейки 1-3: ~3-5 минут
- Ячейка 4 (обучение): ~40-60 минут

После обучения скачай:
- `efficientnet_b0_styles.pth` ← главное
- `classification_report.txt`
- `confusion_matrix.png`

## Шаг 4 — деплой новой модели

Положи `.pth` в `C:\projects\photo-style-classifier\ml-service\weights\`
(перезапиши старый файл).

**Перед** перезапуском контейнеров — нужно обновить config (8 классов
вместо 7) и накатить миграцию `V6__update_taxonomy_to_8_classes.sql`.
Скажи мне когда `.pth` будет готов — я сделаю эти изменения и закоммичу
в один проход, чтобы у тебя не было промежуточного нерабочего состояния.

После моих правок ты выполнишь:
```powershell
cd C:\projects\photo-style-classifier
git pull
docker compose up -d --build backend ml-service
curl http://localhost:8000/health
```

В `/health` должно появиться:
```json
"styles": ["airy", "dark", "dramatic", "golden_hour",
           "minimalist", "monochrome", "neon", "vintage"]
```

## Что мы ожидаем от метрик после переобучения

| Метрика | До (7 классов с moody) | Ожидаемо после (8 без moody) |
|---|---:|---:|
| **Best val accuracy** | 0.724 | **0.75–0.82** |
| `airy` F1 | 0.834 | ≈ |
| `golden_hour` F1 | 0.899 | ≈ |
| `monochrome` F1 | — | **0.90+** (очень разделимый класс) |
| `neon` F1 | — | **0.85+** |
| Слабый класс | `moody` 0.549 | `dramatic` (вероятно остаётся 0.55-0.65) |

Главное — **bias-эффект на moody пропадёт**, потому что класса больше нет.
Модель станет более «честной»: либо уверенно отдаёт правильный класс,
либо распределяет confidence равномерно (out-of-distribution).

## Что использовать в отчёте

Эту итерацию очень удобно расписать в Главе 5 «Анализ результатов» как
**эволюцию методики**:

> Третья итерация ставила задачу повысить per-class robustness через
> пересмотр таксономии. Анализ confusion matrix показал, что класс
> `moody` имеет самый низкий F1 (0.549) и систематически путается с
> dark/dramatic/vintage — это согласуется с гипотезой §1.2 о
> методологической слабости эмоциональных категорий относительно
> чисто визуальных. Класс удалён. Вместо него введены два новых класса
> с однозначно различимыми операциональными определениями: `monochrome`
> (saturation ≤ 0.15) и `neon` (saturation ≥ 0.5 при низком фоновом
> brightness). Точность поднялась до X%, новые классы достигли F1 = Y
> и Z соответственно — что подтверждает гипотезу.

Это очень сильный нарратив на защиту: видно что ты двигался методически
обоснованно, а не «обучил-получил».
