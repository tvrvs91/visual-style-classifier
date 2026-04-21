# Photo Style Classifier

Diploma project: automatic photo classification by visual style using transfer learning.

Three services:

- **backend** — Spring Boot 3 (Java 17), JWT auth, JPA + Flyway on Postgres, MinIO for storage, RabbitMQ for async ML tasks.
- **ml-service** — FastAPI + pika consumer, EfficientNet-B0 with an 8-class head (heuristic fallback when no weights are present).
- **frontend** — React + Vite, with upload, gallery, style filter.

Styles: `moody`, `minimalist`, `street`, `golden_hour`, `dark`, `airy`, `vintage`, `dramatic`.

## Run everything

```bash
docker compose up -d --build
```

Services:
- Frontend (run locally): `cd frontend && npm install && npm run dev` → http://localhost:5173
- Backend: http://localhost:8080
- ML service: http://localhost:8000/health
- RabbitMQ UI: http://localhost:15672 (psc_user / psc_password)
- MinIO console: http://localhost:9001 (psc_admin / psc_admin_password)

## API quick test

```bash
# register
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"secret123"}'

# → copy token into TOKEN, then upload
curl -X POST http://localhost:8080/api/photos \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/photo.jpg"

# list
curl http://localhost:8080/api/photos -H "Authorization: Bearer $TOKEN"

# search
curl "http://localhost:8080/api/photos/search?style=golden_hour&minConfidence=0.2" \
  -H "Authorization: Bearer $TOKEN"
```

## Swap in a real fine-tuned model

Drop a PyTorch `state_dict` for `efficientnet_b0` with a replaced 8-class head into
`ml-service/weights/efficientnet_b0_styles.pth`. The ML service detects it on boot and
switches out of heuristic mode.
