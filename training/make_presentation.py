"""
Генерация .pptx для защиты диплома.

Минималистичный дизайн: чёрный текст на белом, Calibri, без декораций.
13 слайдов, ~5–6 минут речи.

Запуск:
    python training/make_presentation.py

Артефакт:
    docs/diploma-defense.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# --- константы дизайна ----------------------------------------------------

FONT = "Calibri"
BLACK = RGBColor(0x00, 0x00, 0x00)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT_GREY = RGBColor(0xAA, 0xAA, 0xAA)
ACCENT = RGBColor(0xC0, 0x39, 0x2B)  # brand red, used sparingly
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

FIG = Path(__file__).resolve().parent.parent / "docs" / "diploma-latex" / "figures"
UI_IMG = Path(__file__).resolve().parent.parent / "docs" / "figures" / "ui-gallery.png"


# --- утилиты вёрстки ------------------------------------------------------

def set_text(frame, text, font_size=18, bold=False, color=BLACK, align=PP_ALIGN.LEFT):
    p = frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color


def add_textbox(slide, left, top, width, height, text, font_size=18,
                bold=False, color=BLACK, align=PP_ALIGN.LEFT, line_spacing=1.15):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    set_text(tf, text, font_size=font_size, bold=bold, color=color, align=align)
    return box


def add_bullets(slide, left, top, width, height, items, font_size=18,
                color=BLACK, line_spacing=1.25):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(2)
        p.space_after = Pt(6)
        p.line_spacing = line_spacing
        run = p.add_run()
        run.text = "•  " + item
        run.font.name = FONT
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
    return box


def add_header(slide, title, subtitle=None):
    """Заголовок слайда + опциональный подзаголовок + красная полоска."""
    add_textbox(slide, Inches(0.5), Inches(0.35), Inches(12.5), Inches(0.6),
                title, font_size=32, bold=True)
    if subtitle:
        add_textbox(slide, Inches(0.5), Inches(0.95), Inches(12.5), Inches(0.4),
                    subtitle, font_size=16, color=GREY)
    # горизонтальная линия
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                  Inches(0.5), Inches(1.4),
                                  Inches(1.2), Emu(25400))  # 2pt
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT
    line.line.fill.background()


def add_table(slide, left, top, width, height, data,
              font_size=14, header_bold=True, col_widths=None):
    """data = list of lists. First row is header."""
    rows = len(data)
    cols = len(data[0])
    table = slide.shapes.add_table(rows, cols, left, top, width, height).table
    if col_widths:
        for i, w in enumerate(col_widths):
            table.columns[i].width = w
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            cell = table.cell(r, c)
            cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.name = FONT
                    run.font.size = Pt(font_size)
                    run.font.bold = (r == 0 and header_bold)
                    run.font.color.rgb = BLACK
            # тонкая граница
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if r > 0 else RGBColor(0xF0, 0xF0, 0xF0)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
    return table


def add_image_centered(slide, image_path: Path, top, max_w=Inches(10), max_h=Inches(5)):
    if not image_path.exists():
        # плейсхолдер
        ph = slide.shapes.add_textbox(Inches(0.5), top, Inches(12.5), Inches(0.5))
        set_text(ph.text_frame, f"[ИЗОБРАЖЕНИЕ: {image_path.name} — не найдено]",
                 font_size=14, color=LIGHT_GREY, align=PP_ALIGN.CENTER)
        return
    from PIL import Image as PILImage
    with PILImage.open(image_path) as im:
        iw, ih = im.size
    ratio = min(max_w / Inches(1) * 96 / iw, max_h / Inches(1) * 96 / ih)
    target_w = Inches(iw * ratio / 96)
    target_h = Inches(ih * ratio / 96)
    left = (SLIDE_W - target_w) // 2
    slide.shapes.add_picture(str(image_path), left, top,
                             width=target_w, height=target_h)


# --- слайды ---------------------------------------------------------------

def new_blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])  # blank layout


def slide_title(prs):
    s = new_blank(prs)
    # Минвуз + университет — мелким сверху
    add_textbox(s, Inches(0.5), Inches(0.4), Inches(12.5), Inches(0.4),
                "Министерство науки и высшего образования Российской Федерации",
                font_size=12, color=GREY, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(0.5), Inches(0.7), Inches(12.5), Inches(0.4),
                "Ярославский государственный университет имени П.Г. Демидова",
                font_size=12, color=GREY, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(0.5), Inches(1.0), Inches(12.5), Inches(0.4),
                "Кафедра информационных и сетевых технологий",
                font_size=12, color=GREY, align=PP_ALIGN.CENTER)

    # Тема — крупно по центру
    add_textbox(s, Inches(0.5), Inches(2.1), Inches(12.5), Inches(0.7),
                "Разработка системы автоматической",
                font_size=30, bold=True, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(0.5), Inches(2.7), Inches(12.5), Inches(0.7),
                "классификации фотографий по визуальному стилю",
                font_size=30, bold=True, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(0.5), Inches(3.3), Inches(12.5), Inches(0.7),
                "на основе transfer learning",
                font_size=30, bold=True, align=PP_ALIGN.CENTER)

    # Тип работы
    add_textbox(s, Inches(0.5), Inches(4.6), Inches(12.5), Inches(0.5),
                "Выпускная квалификационная работа",
                font_size=18, color=GREY, align=PP_ALIGN.CENTER)

    # Студент и руководитель
    add_textbox(s, Inches(0.5), Inches(5.4), Inches(12.5), Inches(0.5),
                "Студент группы ПИЭ-41БО   Т.Р. Журавлев",
                font_size=18, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(0.5), Inches(5.9), Inches(12.5), Inches(0.5),
                "Научный руководитель: к.п.н., доцент Д.Ю. Чалый",
                font_size=18, align=PP_ALIGN.CENTER)

    add_textbox(s, Inches(0.5), Inches(6.8), Inches(12.5), Inches(0.4),
                "Ярославль, 2026",
                font_size=14, color=GREY, align=PP_ALIGN.CENTER)


def slide_goal_tasks(prs):
    s = new_blank(prs)
    add_header(s, "Цель и задачи работы")

    add_textbox(s, Inches(0.5), Inches(1.7), Inches(12.5), Inches(0.6),
                "Разработать программный комплекс автоматической стилевой классификации",
                font_size=22, bold=True)
    add_textbox(s, Inches(0.5), Inches(2.3), Inches(12.5), Inches(0.5),
                "и провести углублённый эмпирический анализ обученной модели",
                font_size=22, bold=True)

    add_textbox(s, Inches(0.5), Inches(3.1), Inches(12.5), Inches(0.4),
                "Восемь задач:", font_size=18, color=GREY)
    add_bullets(s, Inches(0.5), Inches(3.6), Inches(6), Inches(4), [
        "Сбор и разметка датасета",
        "Обзор методов и выбор архитектуры",
        "Обучение и оценка модели",
        "Микросервисная архитектура",
    ], font_size=17)
    add_bullets(s, Inches(6.8), Inches(3.6), Inches(6), Inches(4), [
        "REST-API с авторизацией JWT",
        "Контейнеризация и CI/CD",
        "Шесть исследовательских экспериментов",
        "Поиск похожих фотографий через embeddings",
    ], font_size=17)


def slide_relevance(prs):
    s = new_blank(prs)
    add_header(s, "Актуальность")

    add_bullets(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(5), [
        "Объёмы цифровой фотографии растут экспоненциально",
        "Существующие системы (Pinterest, Google Photos, Adobe Lightroom) "
        "классифицируют объекты и сцены — не стиль",
        "Стиль (освещение, тональность, композиция) критичен для дизайнеров, "
        "кураторов и стоковых платформ",
        "Ниша open-source self-hosted стилевого классификатора не освоена "
        "коммерческими продуктами",
    ], font_size=22, line_spacing=1.35)


def slide_architecture(prs):
    s = new_blank(prs)
    add_header(s, "Архитектура системы",
               "Микросервисы, асинхронная обработка через очередь сообщений")

    # ASCII-схема компонентов
    box1 = slide_box(s, Inches(0.5), Inches(2.2), Inches(2.5), Inches(1.0),
                    "React SPA\n(Vite, :5173)")
    box2 = slide_box(s, Inches(4.0), Inches(2.2), Inches(2.5), Inches(1.0),
                    "Spring Backend\n(Java 17, :8080)")
    box3 = slide_box(s, Inches(7.5), Inches(2.2), Inches(2.5), Inches(1.0),
                    "FastAPI ML\n(Python, :8000)")
    box4 = slide_box(s, Inches(11.0), Inches(2.2), Inches(2.0), Inches(1.0),
                    "RabbitMQ",
                    color=RGBColor(0xF6, 0xF6, 0xF6))
    box5 = slide_box(s, Inches(4.0), Inches(4.5), Inches(2.5), Inches(0.9),
                    "PostgreSQL",
                    color=RGBColor(0xF6, 0xF6, 0xF6))
    box6 = slide_box(s, Inches(7.5), Inches(4.5), Inches(2.5), Inches(0.9),
                    "MinIO (S3)",
                    color=RGBColor(0xF6, 0xF6, 0xF6))

    # подписи стрелок (текстом)
    add_textbox(s, Inches(2.9), Inches(2.55), Inches(1.2), Inches(0.4),
                "REST/JSON →", font_size=12, color=GREY, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(6.4), Inches(2.55), Inches(1.2), Inches(0.4),
                "AMQP →", font_size=12, color=GREY, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(9.9), Inches(2.55), Inches(1.2), Inches(0.4),
                "←  →", font_size=12, color=GREY, align=PP_ALIGN.CENTER)

    # подвал
    add_bullets(s, Inches(0.5), Inches(6.0), Inches(12.5), Inches(1.5), [
        "Docker Compose · GitHub Actions CI · 11 integration tests (Testcontainers)",
        "ML-сервис масштабируется независимо от backend'а",
    ], font_size=16, color=GREY)


def slide_box(slide, left, top, width, height, text, color=None):
    """Прямоугольник с текстом по центру — для архитектурных схем."""
    if color is None:
        color = WHITE
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.color.rgb = BLACK
    shape.line.width = Pt(1.25)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Emu(50000)
    tf.margin_right = Emu(50000)
    tf.text = ""
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = line
        run.font.name = FONT
        run.font.size = Pt(16)
        run.font.bold = (i == 0)
        run.font.color.rgb = BLACK
    return shape


def slide_stack(prs):
    s = new_blank(prs)
    add_header(s, "Технологический стек")

    headers = ["Backend", "ML-сервис", "Frontend"]
    rows = [
        ["Spring Boot 3", "FastAPI", "React 18"],
        ["Java 17", "Python 3.11", "Vite 5"],
        ["JWT, Spring Security", "PyTorch 2.4", "Axios"],
        ["JPA, Flyway", "EfficientNet-B0", "React Router"],
        ["Testcontainers", "scikit-learn", ""],
    ]
    data = [headers] + rows
    add_table(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(3.5), data,
              font_size=18)

    add_textbox(s, Inches(0.5), Inches(6.0), Inches(12.5), Inches(0.5),
                "Инфраструктура: PostgreSQL 16 · MinIO · RabbitMQ 3.13 · Docker Compose",
                font_size=18, color=GREY, align=PP_ALIGN.CENTER)


def slide_dataset(prs):
    s = new_blank(prs)
    add_header(s, "Датасет",
               "4691 фотография, 8 классов, weak supervision из Unsplash и Pexels API")

    # 8 классов в две строки
    add_textbox(s, Inches(0.5), Inches(1.8), Inches(12.5), Inches(0.6),
                "Восемь классов:", font_size=16, color=GREY)
    add_textbox(s, Inches(0.5), Inches(2.3), Inches(12.5), Inches(0.8),
                "airy   dark   dramatic   golden_hour",
                font_size=24, bold=True, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(0.5), Inches(2.95), Inches(12.5), Inches(0.8),
                "minimalist   monochrome   neon   vintage",
                font_size=24, bold=True, align=PP_ALIGN.CENTER)

    add_textbox(s, Inches(0.5), Inches(4.2), Inches(12.5), Inches(0.4),
                "Обработка:", font_size=16, color=GREY)
    add_bullets(s, Inches(0.5), Inches(4.6), Inches(12.5), Inches(3), [
        "MD5-дедупликация — удалено 102 дубликата",
        "Балансировка: cap 600 фото/класс, дисбаланс с 5× до 1.2×",
        "Stratified split 80/20: 3556 train + 893 val",
    ], font_size=20)


def slide_evolution(prs):
    s = new_blank(prs)
    add_header(s, "Эволюция модели: 4 итерации",
               "EfficientNet-B0 · двухфазный fine-tune · WeightedRandomSampler · label smoothing 0.1")

    data = [
        ["Версия", "Классы", "Val Acc", "Замечание"],
        ["v1", "8 (с moody, street)", "0.678", "Сильный bias на minimalist"],
        ["v2", "7 (без street)", "0.724", "Bias на moody"],
        ["v3", "8 (+monochrome, +neon, −moody)", "0.726", "Bias устранён"],
        ["v3.1", "та же, воспроизводимый split", "0.694", "Финальная модель"],
    ]
    add_table(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(3.5), data,
              font_size=18,
              col_widths=[Inches(1.5), Inches(4.5), Inches(2.0), Inches(4.5)])

    add_textbox(s, Inches(0.5), Inches(6.0), Inches(12.5), Inches(0.6),
                "Удалены жанровые и композитные классы. "
                "Введены операционально определимые (через saturation/brightness).",
                font_size=16, color=GREY, align=PP_ALIGN.CENTER)


def slide_metrics(prs):
    s = new_blank(prs)
    add_header(s, "Финальные метрики v3.1",
               "Accuracy = 0.694   ·   Macro F1 = 0.687   ·   Weighted F1 = 0.692")

    data = [
        ["Класс", "Precision", "Recall", "F1", "Support"],
        ["neon",         "0.908", "0.900", "0.904", "120"],
        ["golden_hour",  "0.774", "0.898", "0.831", "118"],
        ["vintage",      "0.730", "0.743", "0.737", "113"],
        ["airy",         "0.750", "0.696", "0.722", "112"],
        ["minimalist",   "0.604", "0.640", "0.621", "100"],
        ["dark",         "0.620", "0.578", "0.598", "116"],
        ["monochrome",   "0.534", "0.556", "0.545",  "99"],
        ["dramatic",     "0.574", "0.504", "0.537", "115"],
    ]
    add_table(s, Inches(2.0), Inches(2.0), Inches(9.0), Inches(4.5), data,
              font_size=16)

    add_textbox(s, Inches(0.5), Inches(6.7), Inches(12.5), Inches(0.5),
                "Иерархия: neon > golden_hour > vintage / airy > "
                "dark / minimalist > dramatic ≈ monochrome",
                font_size=14, color=GREY, align=PP_ALIGN.CENTER)


def slide_robustness(prs):
    s = new_blank(prs)
    add_header(s, "Устойчивость к перетасовке данных",
               "Главный методологический результат работы")

    add_bullets(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(2), [
        "В первоначальном обучении обнаружено data leakage: val_acc 0.925 (инфлированный)",
        "Реализован воспроизводимый алгоритм train/val split — модель v3.1, честные 0.694",
        "Между двумя независимыми обучениями (v3 → v3.1):",
    ], font_size=20)

    # вложенный список с конкретными числами
    add_bullets(s, Inches(1.5), Inches(4.3), Inches(11.5), Inches(2), [
        "Изменения per-class F1 ≤ 9 процентных пунктов",
        "Иерархия сложности классов полностью сохраняется",
        "Структура топ-путаниц (monochrome ↔ minimalist, dramatic ↔ dark) сохраняется",
    ], font_size=18, color=GREY)

    add_textbox(s, Inches(0.5), Inches(6.5), Inches(12.5), Inches(0.6),
                "Выводы — свойства задачи, а не артефакты разбиения данных",
                font_size=20, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)


def slide_experiments(prs):
    s = new_blank(prs)
    add_header(s, "Шесть исследовательских экспериментов")

    data = [
        ["#", "Эксперимент", "Главный результат"],
        ["E1", "Grad-CAM (интерпретируемость)",
            "Модель смотрит на стилистически осмысленные области"],
        ["E2", "Embeddings + t-SNE / UMAP",
            "k-NN на эмбеддингах = 0.62 (≈ полная модель)"],
        ["E3", "Hand-crafted baseline",
            "RF на 5 признаках = 0.49 → CNN добавляет +20 пп"],
        ["E4", "Temperature scaling",
            "ECE снижен с 0.061 до 0.049 (−20%)"],
        ["E5", "Сравнение с CLIP",
            "CLIP linear probe 0.738 > наш fine-tune 0.694"],
        ["E6", "Multi-label расширение",
            "monochrome F1: 0.545 → 0.934 (+38.9 пп)"],
    ]
    add_table(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(4.5), data,
              font_size=15,
              col_widths=[Inches(0.7), Inches(4.0), Inches(7.8)])


def slide_multilabel(prs):
    s = new_blank(prs)
    add_header(s, "Multi-label расширение",
               "Гипотеза: композитные кадры ломают single-label постановку")

    data = [
        ["Класс", "Single F1", "Multi F1", "Δ"],
        ["monochrome", "0.545", "0.934", "+38.9 пп"],
        ["dark",       "0.598", "0.881", "+28.3 пп"],
        ["dramatic",   "0.537", "0.610", "+7.3 пп"],
        ["minimalist", "0.621", "0.640", "+1.9 пп"],
        ["vintage",    "0.737", "0.716", "−2.1 пп"],
        ["golden_hour","0.831", "0.810", "−2.1 пп"],
        ["neon",       "0.904", "0.838", "−6.6 пп"],
    ]
    add_table(s, Inches(2.5), Inches(2.0), Inches(8.0), Inches(4.0), data,
              font_size=15)

    add_textbox(s, Inches(0.5), Inches(6.3), Inches(12.5), Inches(0.6),
                "mAP = 0.818   ·   Macro F1 = 0.773   ·   Hamming = 0.92",
                font_size=20, bold=True, align=PP_ALIGN.CENTER)


def slide_clip(prs):
    s = new_blank(prs)
    add_header(s, "Сравнение с foundation-моделью CLIP")

    data = [
        ["Подход", "Accuracy", "Macro F1", "Размер", "Обучение"],
        ["EfficientNet-B0 fine-tune", "0.694", "0.687", "16 МБ", "~30 мин T4"],
        ["CLIP linear probe",         "0.738", "0.730", "350 МБ", "<1 мин CPU"],
        ["CLIP zero-shot",            "0.635", "0.616", "350 МБ", "без обучения"],
    ]
    add_table(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(2.5), data,
              font_size=16,
              col_widths=[Inches(4.5), Inches(1.7), Inches(1.7), Inches(2.0),
                          Inches(2.6)])

    add_bullets(s, Inches(0.5), Inches(5.0), Inches(12.5), Inches(2.5), [
        "CLIP linear probe превосходит наш fine-tune на +4.4 пп",
        "CLIP представления обучены на 400M пар (изображение, текст) — "
        "уже содержат стилевую семантику",
        "Направление развития: CLIP в production при GPU-инференсе",
    ], font_size=18)


def slide_ui(prs):
    s = new_blank(prs)
    add_header(s, "Реализованный программный комплекс",
               "React frontend · Spring backend · FastAPI ML")

    if UI_IMG.exists():
        add_image_centered(s, UI_IMG, Inches(1.7), max_w=Inches(12), max_h=Inches(5.4))
    else:
        add_textbox(s, Inches(0.5), Inches(3.5), Inches(12.5), Inches(0.5),
                    f"[Сюда вставить скриншот интерфейса: {UI_IMG.name}]",
                    font_size=14, color=LIGHT_GREY, align=PP_ALIGN.CENTER)


def slide_future(prs):
    s = new_blank(prs)
    add_header(s, "Направления развития")

    add_bullets(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(5), [
        "Ручная multi-label разметка ~1000 фотографий",
        "Переход на CLIP linear probe в production",
        "Fine-tune CLIP методом LoRA для адаптации к датасету",
        "Векторный поиск похожих через pgvector + HNSW-индекс",
        "Stratified k-fold cross-validation для confidence intervals",
        "Persistent split вместе с весами в постоянное хранилище",
    ], font_size=22, line_spacing=1.4)


def slide_conclusion(prs):
    s = new_blank(prs)
    add_header(s, "Заключение")

    add_textbox(s, Inches(0.5), Inches(2.0), Inches(12.5), Inches(0.5),
                "Восемь поставленных задач выполнены",
                font_size=24, bold=True, align=PP_ALIGN.CENTER)

    add_textbox(s, Inches(0.5), Inches(2.9), Inches(12.5), Inches(0.4),
                "Пять ключевых результатов:",
                font_size=16, color=GREY, align=PP_ALIGN.LEFT)

    add_bullets(s, Inches(0.5), Inches(3.4), Inches(12.5), Inches(3.5), [
        "Устойчивость метрик к перетасовке валидационной выборки",
        "Операциональная определимость классов через статистики признаков",
        "Подтверждена интерпретируемость модели через Grad-CAM",
        "Multi-label трансформация monochrome: F1 0.545 → 0.934",
        "Foundation-модель CLIP превосходит fine-tune (направление развития)",
    ], font_size=20, line_spacing=1.35)

    add_textbox(s, Inches(0.5), Inches(6.7), Inches(12.5), Inches(0.5),
                "Исходный код, обученные веса и артефакты экспериментов — MIT",
                font_size=14, color=GREY, align=PP_ALIGN.CENTER)


# --- финал ----------------------------------------------------------------

def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide_title(prs)        # 1
    slide_goal_tasks(prs)   # 2
    slide_relevance(prs)    # 3
    slide_architecture(prs) # 4
    slide_stack(prs)        # 5
    slide_dataset(prs)      # 6
    slide_evolution(prs)    # 7
    slide_metrics(prs)      # 8
    slide_robustness(prs)   # 9
    slide_experiments(prs)  # 10
    slide_multilabel(prs)   # 11
    slide_clip(prs)         # 12
    slide_ui(prs)           # 13 — скриншот интерфейса
    slide_future(prs)       # 14
    slide_conclusion(prs)   # 15

    out = Path(__file__).resolve().parent.parent / "docs" / "diploma-defense.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    print(f"saved: {out}")
    print(f"slides: {len(prs.slides)}")


if __name__ == "__main__":
    build()
