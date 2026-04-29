# Visual Style Classifier

[![CI](https://github.com/tvrvs91/visual-style-classifier/actions/workflows/ci.yml/badge.svg)](https://github.com/tvrvs91/visual-style-classifier/actions/workflows/ci.yml)
[![Java](https://img.shields.io/badge/Java-17-007396?logo=openjdk)](https://openjdk.org/projects/jdk/17/)
[![Spring Boot](https://img.shields.io/badge/Spring_Boot-3.3-6DB33F?logo=springboot)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4-EE4C2C?logo=pytorch)](https://pytorch.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?logo=vite)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docs.docker.com/compose/)

Дипломный проект — **автоматическая классификация фотографий по визуальному стилю** на основе transfer learning. Загружаешь фото → нейросеть EfficientNet-B0 определяет стиль (`moody`, `minimalist`, `street`, `golden_hour`, `dark`, `airy`, `vintage`, `dramatic`) → результат отображается в галерее с фильтрами и поиском похожих фото.

## Архитектура

```
┌──────────────┐  REST/JSON  ┌──────────────────┐
│  React SPA   │ ──────────► │  Spring Backend  │
│   :5173      │             │   :8080 (JWT)    │
└──────────────┘             └────────┬─────────┘
                                      │
              ┌───────────────────────┼─────────────────────┐
              ▼                       ▼                     ▼
      ┌──────────────┐        ┌──────────────┐      ┌──────────────┐
      │  PostgreSQL  │        │    MinIO     │      │   RabbitMQ   │
      │   :5432      │        │   :9000 (S3) │      │   :5672      │
      └──────────────┘        └──────┬───────┘      └──────┬───────┘
                                     │ download            │ consume
                                     │                     │
                                     │       ┌─────────────▼──────────────┐
                                     └──────►│   FastAPI ML service       │
                                             │   :8000 / EfficientNet-B0  │
                                             └────────────────────────────┘
```

## Стек

| Слой | Технологии |
|---|---|
| **Backend** | Spring Boot 3.3, Java 17, Spring Security (JWT), Spring Data JPA, Flyway, Spring AMQP, MinIO Java SDK |
| **ML** | Python 3.11, FastAPI, PyTorch 2.4 + torchvision, EfficientNet-B0, pika, boto3, Pillow |
| **Frontend** | React 18, Vite 5, React Router, Axios |
| **Infrastructure** | PostgreSQL 16, RabbitMQ 3.13, MinIO, Docker Compose |
| **CI** | GitHub Actions (build + test + image build) |

## Скриншоты

> *(скриншоты добавляются в `docs/screenshots/` — заменить плейсхолдеры на реальные после первого деплоя)*

| Галерея | Модалка с анализом | Загрузка |
|---|---|---|
| ![gallery](docs/screenshots/gallery.png) | ![modal](docs/screenshots/modal.png) | ![upload](docs/screenshots/upload.png) |

## Запуск

```bash
git clone https://github.com/tvrvs91/visual-style-classifier.git
cd visual-style-classifier

# 1. Поднимаем инфраструктуру + backend + ML (первый build долгий — torch ~800 МБ)
docker compose up -d --build

# 2. Frontend в dev-режиме
cd frontend
npm install
npm run dev
```

Точки входа после старта:

| URL | Назначение |
|---|---|
| http://localhost:5173 | Клиент |
| http://localhost:8080 | Backend REST API |
| http://localhost:8000/health | ML service health |
| http://localhost:9001 | MinIO console (`psc_admin` / `psc_admin_password`) |
| http://localhost:15672 | RabbitMQ UI (`psc_user` / `psc_password`) |
| `localhost:55432` | PostgreSQL (мапится на 55432 чтобы не конфликтовать с локальным) |

## REST API

Все эндпоинты под `/api/photos` и `/api/styles` требуют JWT в заголовке `Authorization: Bearer <token>`.

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/auth/register` | Регистрация |
| POST | `/api/auth/login` | Аутентификация |
| GET | `/api/photos` | Список своих фото (пагинация) |
| GET | `/api/photos/{id}` | Одна фотография |
| POST | `/api/photos` | Загрузка (multipart) |
| DELETE | `/api/photos/{id}` | Удаление |
| GET | `/api/photos/search?style=X&minConfidence=0.2` | Поиск по стилю |
| GET | `/api/styles` | Список стилей |

Пример:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"secret123"}' | jq -r .token)

curl -X POST http://localhost:8080/api/photos \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg"
```

## Подключение обученной модели

ML-сервис стартует в эвристическом режиме (классификация по статистикам изображения), пока в `ml-service/weights/` нет файла весов. Чтобы переключиться в режим нейросети, помести туда `state_dict` дообученного EfficientNet-B0 (последний слой — `Linear(1280, 8)`):

```bash
cp путь/к/efficientnet_b0_styles.pth ml-service/weights/
docker compose restart ml-service
```

В логах появится `Loaded fine-tuned weights from /app/weights/efficientnet_b0_styles.pth`.

## Структура репозитория

```
.
├── backend/                Spring Boot 3 (Java 17)
├── ml-service/             FastAPI + PyTorch
├── frontend/               React + Vite
├── docker-compose.yml
├── .github/workflows/      CI pipelines
├── docs/
│   ├── REPORT.md           Дипломный отчёт
│   ├── work-log.md         Журнал реализации (по итерациям)
│   └── screenshots/
└── README.md
```

## Разработка

```bash
# Backend локально (нужна Java 17 + Maven)
cd backend && mvn spring-boot:run

# ML локально
cd ml-service && pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev

# Прогон тестов
cd backend && mvn test
```

## Лицензия

MIT
