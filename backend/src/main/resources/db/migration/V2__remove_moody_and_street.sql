-- Удаляем классы `moody` и `street` как методологически слабые:
-- `moody` — эмоциональная категория, перекрывается с dark/dramatic/vintage.
-- `street` — жанровая (про сюжет), а не стилистическая категория.
-- Подробное обоснование — в docs/REPORT.md §1.2 и training/ANALYSIS.md.
--
-- ON DELETE CASCADE на photo_styles.style_id в V1 миграции автоматически
-- удалит связи photo↔style. Сами фото остаются — просто теряют эти теги.

DELETE FROM styles WHERE name IN ('moody', 'street');
