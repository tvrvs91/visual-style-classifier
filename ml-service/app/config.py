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

    model_weights_path: str = "/app/weights/efficientnet_b0_styles.pth"
    top_k: int = 3

    styles: list[str] = [
        "moody",
        "minimalist",
        "street",
        "golden_hour",
        "dark",
        "airy",
        "vintage",
        "dramatic",
    ]


settings = Settings()
