import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .classifier import StyleClassifier
from .config import settings
from .minio_client import download_bytes
from .rabbitmq_consumer import RabbitMQWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("ml-service")


classifier = StyleClassifier()


def handle_task(task: dict) -> dict:
    photo_id = task.get("photoId")
    s3_key = task.get("s3Key")
    bucket = task.get("bucket") or settings.minio_bucket

    if photo_id is None or not s3_key:
        return {
            "photoId": photo_id,
            "status": "ERROR",
            "error": "missing photoId or s3Key",
            "styles": [],
        }

    try:
        data = download_bytes(bucket, s3_key)
        predictions = classifier.predict(data)
        return {
            "photoId": photo_id,
            "status": "OK",
            "error": None,
            "styles": [{"name": name, "confidence": float(conf)} for name, conf in predictions],
        }
    except Exception as e:
        log.exception("Classification failed for photoId=%s", photo_id)
        return {
            "photoId": photo_id,
            "status": "ERROR",
            "error": str(e),
            "styles": [],
        }


worker = RabbitMQWorker(handle_task)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker.start()
    log.info("ML service started (heuristic mode: %s)", classifier.use_heuristic)
    yield
    worker.stop()


app = FastAPI(title="Photo Style ML Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "heuristic_mode": classifier.use_heuristic,
        "styles": classifier.styles,
    }


@app.post("/classify-debug")
def classify_debug(task: dict):
    return handle_task(task)
