-- Финальная таксономия v3 — 8 операционально определимых классов:
--   airy, dark, dramatic, golden_hour, minimalist, monochrome, neon, vintage
--
-- Удаление moody (как методологически слабого эмоционального класса),
-- добавление monochrome и neon как явно различимых по визуальным метрикам:
--   monochrome — saturation ≈ 0 (B&W любых оттенков)
--   neon       — высокая насыщенность + тёмный фон (киберпанк/синтвейв)
--
-- ON DELETE CASCADE на photo_styles.style_id автоматически удалит
-- связи photo↔moody. Сами фото остаются — потеряют только moody-теги.

DELETE FROM styles WHERE name = 'moody';

INSERT INTO styles (name) VALUES ('monochrome') ON CONFLICT (name) DO NOTHING;
INSERT INTO styles (name) VALUES ('neon')       ON CONFLICT (name) DO NOTHING;
