CREATE TABLE users (
    id         BIGSERIAL PRIMARY KEY,
    email      VARCHAR(255) NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE styles (
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE photos (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    s3_key      VARCHAR(512) NOT NULL,
    uploaded_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(16)  NOT NULL DEFAULT 'PENDING'
);

CREATE INDEX idx_photos_user_id ON photos (user_id);
CREATE INDEX idx_photos_status  ON photos (status);

CREATE TABLE photo_styles (
    photo_id   BIGINT         NOT NULL REFERENCES photos (id) ON DELETE CASCADE,
    style_id   BIGINT         NOT NULL REFERENCES styles (id) ON DELETE CASCADE,
    confidence DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (photo_id, style_id)
);

CREATE INDEX idx_photo_styles_style_id ON photo_styles (style_id);

INSERT INTO styles (name) VALUES
    ('moody'),
    ('minimalist'),
    ('street'),
    ('golden_hour'),
    ('dark'),
    ('airy'),
    ('vintage'),
    ('dramatic');
