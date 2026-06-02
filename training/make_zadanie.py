"""
Генерация бланка «Задание на ВКР» (.docx) с заполненными данными.

Типовая структура задания на выпускную квалификационную работу ЯрГУ.

Запуск:
    python training/make_zadanie.py

Артефакт:
    docs/zadanie-vkr.docx
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


STUDENT_FIO = "Журавлев Тарас Русланович"
STUDENT_GROUP = "ПИЭ-41 БО"
DIRECTION = "09.03.03 Прикладная информатика"
DEPARTMENT = "Информационных и сетевых технологий"
UNIVERSITY = "Ярославский государственный университет им. П.Г. Демидова"
ADVISOR = "Чалый Дмитрий Юрьевич, к.п.н., доцент"
CHAIR = "Чалый Дмитрий Юрьевич"
TOPIC = ("Разработка системы автоматической классификации фотографий "
         "по визуальному стилю на основе transfer learning")
DATE_ISSUE = "27 апреля 2026 г."
DATE_DUE = "26 мая 2026 г."
YEAR = "2026"


def set_font(run, size=12, bold=False, name="Times New Roman", italic=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    for a in ('w:eastAsia', 'w:cs', 'w:ascii', 'w:hAnsi'):
        rfonts.set(qn(a), name)


def para(doc, text, size=12, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT,
         space_after=4, italic=False, indent=None):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if indent is not None:
        p.paragraph_format.left_indent = Cm(indent)
    run = p.add_run(text)
    set_font(run, size=size, bold=bold, italic=italic)
    return p


def field(doc, label, value, size=12):
    """Строка 'метка: значение' где значение жирным."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r1 = p.add_run(label + " ")
    set_font(r1, size=size)
    r2 = p.add_run(value)
    set_font(r2, size=size, bold=True)
    return p


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2)
    sec.bottom_margin = Cm(2)
    sec.left_margin = Cm(3)
    sec.right_margin = Cm(1.5)

    # Шапка
    para(doc, "МИНОБРНАУКИ РОССИИ", size=11, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, f"ФГБОУ ВО «{UNIVERSITY}»", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, f"Кафедра {DEPARTMENT.lower()}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=18)

    # Утверждаю
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("УТВЕРЖДАЮ\nЗаведующий кафедрой\n______________ " + CHAIR
                  + f"\n«___» __________ {YEAR} г.")
    set_font(r, size=12)
    doc.add_paragraph()

    # Заголовок
    para(doc, "ЗАДАНИЕ", size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(doc, "на выпускную квалификационную работу", size=13, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    field(doc, "Студенту", f"{STUDENT_FIO}, группа {STUDENT_GROUP}")
    field(doc, "Направление подготовки:", DIRECTION)
    doc.add_paragraph()

    # 1. Тема
    para(doc, "1. Тема работы:", size=12, bold=True, space_after=2)
    para(doc, TOPIC, size=12, bold=True, space_after=4)
    para(doc, f"утверждена приказом по университету от «___» __________ {YEAR} г.",
         size=11, italic=True, space_after=10)

    # 2. Срок сдачи
    field(doc, "2. Срок сдачи студентом законченной работы:", DATE_DUE)
    doc.add_paragraph()

    # 3. Исходные данные
    para(doc, "3. Исходные данные к работе:", size=12, bold=True, space_after=4)
    for item in [
        "набор фотографий, собираемый через открытые API стоковых сервисов "
        "Unsplash и Pexels;",
        "предобученная свёрточная нейронная сеть EfficientNet-B0 "
        "(библиотека torchvision);",
        "программные средства: Python 3.11 (PyTorch, FastAPI, scikit-learn), "
        "Java 17 (Spring Boot), React (Vite);",
        "инфраструктурные компоненты: PostgreSQL, MinIO, RabbitMQ, Docker;",
        "научная литература по transfer learning и классификации изображений.",
    ]:
        para(doc, "– " + item, size=12, space_after=3, indent=0.5)
    doc.add_paragraph()

    # 4. Содержание
    para(doc, "4. Содержание работы (перечень подлежащих разработке вопросов):",
         size=12, bold=True, space_after=4)
    for i, item in enumerate([
        "обзор методов классификации изображений и обоснование выбора "
        "архитектуры нейронной сети;",
        "сбор, разметка, предобработка и балансировка датасета фотографий "
        "по стилевым категориям;",
        "обучение модели классификации методом transfer learning, "
        "оценка качества на отложенной выборке;",
        "проектирование микросервисной архитектуры системы;",
        "реализация серверной части, ML-сервиса и клиентского "
        "веб-приложения;",
        "проведение исследовательских экспериментов (интерпретируемость, "
        "качество представлений, сравнение с альтернативными моделями, "
        "калибровка, multi-label);",
        "развёртывание, тестирование и анализ результатов работы системы.",
    ], 1):
        para(doc, f"{i}) {item}", size=12, space_after=3, indent=0.5)
    doc.add_paragraph()

    # 5. Иллюстративный материал
    para(doc, "5. Перечень графического (иллюстративного) материала:",
         size=12, bold=True, space_after=4)
    for item in [
        "схема микросервисной архитектуры системы и диаграмма потока данных;",
        "таблицы метрик качества модели, матрицы ошибок (confusion matrix);",
        "графики процесса обучения и визуализации экспериментов "
        "(Grad-CAM, t-SNE, диаграммы калибровки);",
        "скриншоты пользовательского интерфейса.",
    ]:
        para(doc, "– " + item, size=12, space_after=3, indent=0.5)
    doc.add_paragraph()

    field(doc, "6. Дата выдачи задания:", DATE_ISSUE)
    doc.add_paragraph()
    doc.add_paragraph()

    # Подписи
    para(doc, "Руководитель ВКР: ____________________ / " + ADVISOR + " /",
         size=12, space_after=14)
    para(doc, "Задание принял к исполнению: ____________________ / "
              + STUDENT_FIO + " /", size=12, space_after=14)
    para(doc, f"«___» __________ {YEAR} г.", size=12)

    out = Path(__file__).resolve().parent.parent / "docs" / "zadanie-vkr.docx"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    build()
