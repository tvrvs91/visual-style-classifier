"""
Генерация дневника преддипломной практики (.docx) с заполненными данными.

Данные:
- Студент: Журавлев Тарас Русланович, группа ПИЭ-41БО, 4 курс
- Направление: 09.03.03 Прикладная информатика
- Руководитель: Чалый Дмитрий Юрьевич, к.п.н., доцент
- Сроки: 27.04.2026 — 26.05.2026
- База: Кафедра информационных и сетевых технологий, ЯрГУ им. П.Г. Демидова
- Тема ВКР: Разработка системы автоматической классификации фотографий
  по визуальному стилю на основе transfer learning

Запуск:
    python training/make_dnevnik.py

Артефакт:
    docs/dnevnik-praktiki.docx
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


STUDENT_FIO = "Журавлев Тарас Русланович"
STUDENT_GROUP = "ПИЭ-41 БО"
STUDENT_COURSE = "4"
DIRECTION_CODE = "09.03.03"
DIRECTION_NAME = "Прикладная информатика"
PRACTICE_TYPE = "Преддипломная практика"
DATE_START = "27 апреля 2026 г."
DATE_END = "26 мая 2026 г."
YEAR = "2026"
DEPARTMENT = "Информационных и сетевых технологий"
UNIVERSITY = "Ярославский государственный университет им. П.Г. Демидова"

ADVISOR_FIO = "Чалый Дмитрий Юрьевич"
ADVISOR_STATUS = "кандидат педагогических наук, доцент"

THESIS_TOPIC = ("Разработка системы автоматической классификации фотографий "
                "по визуальному стилю на основе transfer learning")


def set_font(run, size=12, bold=False, name="Times New Roman"):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    rfonts.set(qn('w:eastAsia'), name)
    rfonts.set(qn('w:cs'), name)
    rfonts.set(qn('w:ascii'), name)
    rfonts.set(qn('w:hAnsi'), name)


def add_para(doc, text, size=12, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT,
             space_after=0):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    run = p.add_run(text)
    set_font(run, size=size, bold=bold)
    return p


def add_label_value(doc, label, value, label_width=None):
    """Строка вида 'Метка: значение'."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(0)
    r1 = p.add_run(label + "\t")
    set_font(r1, size=12)
    r2 = p.add_run(value)
    set_font(r2, size=12, bold=True)
    return p


def set_cell_text(cell, text, size=10, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    set_font(run, size=size, bold=bold)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def build():
    doc = Document()

    # Стили страницы — стандартные поля A4
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(3)
    section.right_margin = Cm(1.5)

    # Шапка университета — мелким сверху
    add_para(doc, "МИНОБРНАУКИ РОССИИ", size=11, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "Федеральное государственное бюджетное образовательное",
             size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "учреждение высшего образования",
             size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, f"«{UNIVERSITY}»", size=11, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)

    add_para(doc, DEPARTMENT, size=11, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER)
    add_para(doc, "(наименование выпускающей кафедры)", size=9,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)

    # Заголовок
    add_para(doc, "ДНЕВНИК ПРАКТИКИ", size=20, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)

    # Сведения о студенте
    add_label_value(doc, "Студент", STUDENT_FIO)
    add_label_value(doc, "Курс:", STUDENT_COURSE)
    add_label_value(doc, "Форма обучения:", "очная")
    add_label_value(doc, "Учебная группа:", STUDENT_GROUP)
    add_label_value(doc, "Направление подготовки:",
                    f"{DIRECTION_CODE} {DIRECTION_NAME}")
    doc.add_paragraph()

    add_label_value(doc, "Вид практики:", PRACTICE_TYPE)
    add_label_value(doc, "Сроки практики:", f"с {DATE_START} по {DATE_END}")
    add_label_value(doc, "База практики:",
                    f"Кафедра {DEPARTMENT.lower()}, ЯрГУ им. П.Г. Демидова")
    doc.add_paragraph()

    add_para(doc, "Руководитель практики от Университета:", size=12,
             space_after=4)
    add_para(doc, f"{ADVISOR_FIO}, {ADVISOR_STATUS}", size=12, bold=True,
             space_after=2)
    add_para(doc, "(ФИО, учёная степень, учёное звание, должность)", size=9)
    doc.add_paragraph()

    add_label_value(doc, "Тема ВКР:", THESIS_TOPIC)
    doc.add_paragraph()
    doc.add_paragraph()

    add_para(doc, f"Ярославль {YEAR}", size=12, bold=True,
             align=WD_ALIGN_PARAGRAPH.CENTER)

    # ── Страница 2 — Календарный план ─────────────────────────────────────
    doc.add_page_break()

    add_para(doc,
             "Календарно-тематический план-график практики, "
             "сведения о выполняемой работе",
             size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             space_after=12)

    plan = [
        # (№, Вид деятельности, Срок/часы, Дата, Наименование, Часов, Оценка, Подпись)
        ("1", "Установочная конференция",
         "27.04.2026\n2 ч", "27.04.2026",
         "Получение индивидуального задания на практику, ознакомление "
         "с программой и календарным планом, инструктаж по технике "
         "безопасности и информационной безопасности.",
         "2", "", ""),

        ("2", "Этапы работы над выпускной квалификационной работой",
         "28.04 — 25.05.2026\n156 ч", "", "", "", "", ""),

        ("2.1", "Обзор предметной области и методов",
         "28.04 — 03.05.2026\n24 ч", "28.04 — 03.05.2026",
         "Изучение литературы по задаче классификации изображений по "
         "визуальному стилю. Сравнительный анализ архитектур свёрточных "
         "нейронных сетей (EfficientNet, ResNet, MobileNet). Обоснование "
         "выбора подхода transfer learning. Обзор существующих "
         "программных аналогов (Pinterest, Adobe Lightroom, академические "
         "работы Flickr-Style, AVA). Формулировка цели и задач работы.",
         "24", "", ""),

        ("2.2", "Сбор и предобработка датасета",
         "04.05 — 10.05.2026\n28 ч", "04.05 — 10.05.2026",
         "Сбор изображений через API Unsplash и Pexels по восьми "
         "стилевым категориям (airy, dark, dramatic, golden_hour, "
         "minimalist, monochrome, neon, vintage). MD5-дедупликация. "
         "Балансировка классов с пересмотром таксономии. Реализация "
         "воспроизводимого алгоритма разделения на train/val (80/20).",
         "28", "", ""),

        ("2.3", "Обучение модели классификации",
         "11.05 — 15.05.2026\n32 ч", "11.05 — 15.05.2026",
         "Реализация двухфазного fine-tuning EfficientNet-B0 на собственном "
         "датасете (PyTorch). Гиперпараметры: CosineAnnealingLR, label "
         "smoothing 0.1, WeightedRandomSampler, mixed precision. "
         "Обнаружение и устранение data leakage. Получение финальной "
         "модели v3.1 с val accuracy 0.694.",
         "32", "", ""),

        ("2.4", "Разработка программного комплекса",
         "11.05 — 17.05.2026\n28 ч", "11.05 — 17.05.2026",
         "Проектирование микросервисной архитектуры из пяти компонентов. "
         "Реализация backend на Spring Boot 3 (REST API, JWT, Flyway, "
         "интеграция с MinIO и RabbitMQ). Реализация ML-сервиса на "
         "FastAPI + PyTorch. Реализация React-фронта с masonry-галереей, "
         "загрузкой и поиском похожих фотографий. Контейнеризация через "
         "Docker Compose. Настройка CI через GitHub Actions, "
         "интеграционные тесты через Testcontainers.",
         "28", "", ""),

        ("2.5", "Исследовательские эксперименты",
         "18.05 — 22.05.2026\n24 ч", "18.05 — 22.05.2026",
         "Шесть углублённых экспериментов: Grad-CAM (интерпретируемость "
         "модели), анализ embedding-пространства методами t-SNE и UMAP, "
         "статистический анализ ручных признаков (ANOVA), калибровка "
         "вероятностей через temperature scaling, сравнение с "
         "foundation-моделью CLIP (linear probe и zero-shot), переход "
         "к multi-label постановке задачи.",
         "24", "", ""),

        ("2.6", "Оформление выпускной квалификационной работы",
         "23.05 — 25.05.2026\n20 ч", "23.05 — 25.05.2026",
         "Подготовка пояснительной записки ВКР по ГОСТ 7.32-2017: "
         "оформление шести глав, реферата, заключения, списка "
         "литературы (30 источников). Подготовка таблиц, рисунков, "
         "диаграмм и приложений. Подготовка презентации к защите.",
         "20", "", ""),

        ("3", "Отчётная конференция",
         "26.05.2026\n2 ч", "26.05.2026",
         "Защита отчёта о прохождении практики. Сдача дневника и отчёта "
         "научному руководителю.",
         "2", "", ""),
    ]

    # Создаём таблицу 8 столбцов
    headers = [
        "№\nп/п",
        "Вид деятельности",
        "Календарный срок / кол-во часов",
        "Дата",
        "Наименование работы",
        "Кол-во отработанных часов",
        "Оценка по итогам",
        "Подпись руководителя",
    ]
    table = doc.add_table(rows=1 + len(plan), cols=8)
    table.style = "Table Grid"
    table.autofit = False

    # Ширины колонок (в сумме ~16 см при поле 30мм слева + 15мм справа от A4)
    widths_cm = [0.9, 2.6, 2.0, 1.8, 4.5, 1.3, 1.5, 1.4]
    for r in table.rows:
        for i, c in enumerate(r.cells):
            c.width = Cm(widths_cm[i])

    # Шапка таблицы
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, size=9, bold=True,
                      align=WD_ALIGN_PARAGRAPH.CENTER)

    # Тело таблицы
    for r, row in enumerate(plan, start=1):
        for c, val in enumerate(row):
            align = (WD_ALIGN_PARAGRAPH.CENTER if c in (0, 2, 3, 5, 6, 7)
                     else WD_ALIGN_PARAGRAPH.LEFT)
            set_cell_text(table.rows[r].cells[c], val, size=9, align=align)

    doc.add_paragraph()
    add_para(doc, "ИТОГО: 160 часов", size=12, bold=True,
             align=WD_ALIGN_PARAGRAPH.RIGHT, space_after=24)

    # Подписи
    add_para(doc, "Студент: ____________________ / Т.Р. Журавлев /",
             size=12, space_after=24)
    add_para(doc, "Руководитель практики: ____________________ / "
                  "Д.Ю. Чалый /", size=12, space_after=12)
    add_para(doc, f"«___» ___________ {YEAR} г.", size=12)

    # ── Страница 3 — Отзыв руководителя (опционально) ─────────────────────
    doc.add_page_break()
    add_para(doc, "Отзыв руководителя практики о работе студента",
             size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
             space_after=12)

    add_para(doc,
             "В период прохождения преддипломной практики с "
             f"{DATE_START} по {DATE_END} студент {STUDENT_FIO} "
             "выполнял исследовательскую и инженерную работу в рамках "
             "выпускной квалификационной работы на тему: ",
             size=12, space_after=4)
    add_para(doc, f"«{THESIS_TOPIC}».", size=12, bold=True, space_after=12)

    add_para(doc,
             "За период практики студентом самостоятельно собран и "
             "размечен датасет из 4691 фотографии в восьми стилевых "
             "категориях; реализована и обучена свёрточная нейронная "
             "сеть EfficientNet-B0 на собственном датасете с "
             "применением подхода transfer learning; спроектирован и "
             "реализован программный комплекс из пяти микросервисов "
             "(Spring Boot backend, FastAPI ML-сервис, React-клиент, "
             "PostgreSQL, MinIO, RabbitMQ); проведено шесть "
             "исследовательских экспериментов с анализом полученных "
             "результатов. На одном из этапов студентом была "
             "обнаружена неточность в исходной процедуре разделения "
             "данных на обучающую и валидационную выборки; разработан "
             "и применён воспроизводимый алгоритм разделения, после "
             "чего модель была переобучена и получены корректные метрики "
             "качества.",
             size=12, space_after=12)

    add_para(doc,
             "Программа практики выполнена в полном объёме. Студент "
             "проявил инициативу, самостоятельность, способность к "
             "критическому анализу собственных результатов. Дневник "
             "практики оформлен надлежащим образом.",
             size=12, space_after=12)

    add_para(doc, "Оценка по итогам практики: «отлично»", size=12, bold=True,
             space_after=24)

    add_para(doc,
             "Руководитель практики: ____________________ / "
             "Д.Ю. Чалый /", size=12, space_after=12)
    add_para(doc, f"«___» ___________ {YEAR} г.", size=12)

    out = Path(__file__).resolve().parent.parent / "docs" / "dnevnik-praktiki.docx"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    build()
