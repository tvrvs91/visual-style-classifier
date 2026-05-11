-- Расширенные ML-фичи каждой фотографии:
-- * embedding — 1280-мерный вектор предпоследнего слоя EfficientNet-B0
--   (выход после avgpool, до классифицирующей головы). Используется для
--   поиска визуально похожих кадров через cosine similarity.
-- * palette  — 5 доминирующих цветов в hex, извлечены через k-means по RGB.
-- * scores   — 5 количественных атрибутов (brightness, contrast, saturation,
--   warmth, sharpness) в диапазоне [0, 1], детерминированно из пиксельной
--   статистики.
--
-- Хранятся в отдельной таблице 1:1 с photos, чтобы не утяжелять
-- основную сущность 25KB JSON-полей при стандартных listing-запросах.

CREATE TABLE photo_features (
    photo_id     BIGINT PRIMARY KEY REFERENCES photos (id) ON DELETE CASCADE,
    embedding    TEXT      NOT NULL,
    palette      TEXT      NOT NULL,
    scores       TEXT      NOT NULL,
    extracted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
