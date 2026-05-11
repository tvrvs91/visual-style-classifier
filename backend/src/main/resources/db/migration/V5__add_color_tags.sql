-- Добавляем колонку color_tags для фильтрации галереи по доминирующему цвету.
-- Значение — JSON-массив строк из набора color families:
--   ["red", "orange", "yellow", "green", "blue", "purple", "pink", "brown", "neutral"]
-- Вычисляется backend'ом из photo_features.palette при сохранении фичей
-- (см. ColorClassifier и ClassificationConsumer.saveFeatures).
--
-- Существующие строки получают NULL — они не будут найдены поиском по цвету
-- (но останутся видимыми в общей галерее). Для backfill достаточно перезалить
-- фото или запустить будущий /admin/reanalyze-endpoint.

ALTER TABLE photo_features ADD COLUMN color_tags TEXT;
