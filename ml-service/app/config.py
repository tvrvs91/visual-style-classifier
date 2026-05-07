from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "psc_user"
    rabbitmq_password: str = "psc_password"

    task_queue: str = "classification.tasks"
    result_queue: str = "classification.results"
    exchange: str = "classification.exchange"
    task_routing_key: str = "classification.task"
    result_routing_key: str = "classification.result"

    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "psc_admin"
    minio_secret_key: str = "psc_admin_password"
    minio_bucket: str = "photos"

    # Каноничный путь, по которому ML-сервис ищет дообученные веса.
    # Если его нет — пробуются альтернативные имена (см. classifier._resolve_weights_path).
    model_weights_path: str = "/app/weights/efficientnet_b0_styles.pth"
    weights_dir: str = "/app/weights"
    top_k: int = 3

    # Test-time augmentation: усреднение softmax по N аугментациям одного кадра.
    # Стабильно даёт +1–2 пп точности ценой ~×N времени инференса.
    # 1 = выкл, 4 = типичное значение (orig + hflip + 2 random crops).
    use_tta: bool = False
    tta_passes: int = 4

    # Классы в АЛФАВИТНОМ порядке — индексы здесь должны совпадать с порядком,
    # в котором тренировалась голова модели (state_dict выходного Linear).
    styles: list[str] = [
        "airy",
        "dark",
        "dramatic",
        "golden_hour",
        "minimalist",
        "moody",
        "street",
        "vintage",
    ]


settings = Settings()
