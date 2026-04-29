# UML-диаграммы

GitHub нативно рендерит Mermaid-блоки. Эти диаграммы используются как иллюстрации в дипломном отчёте (`docs/REPORT.md`, главы 2 и 3) и как самостоятельный материал для защиты.

---

## 1. Component diagram

Развёртывание системы и связи между компонентами.

```mermaid
flowchart LR
    Browser([Browser])
    React[React SPA<br/>Vite :5173]
    Spring[Spring Boot Backend<br/>:8080]
    Postgres[(PostgreSQL<br/>:5432)]
    MinIO[(MinIO<br/>S3 :9000)]
    Rabbit{{RabbitMQ<br/>:5672}}
    ML[FastAPI ML Service<br/>EfficientNet-B0 :8000]

    Browser -- "HTTPS / JSON" --> React
    React   -- "REST + JWT"   --> Spring
    Browser -- "presigned URL" --> MinIO

    Spring  -- "JPA + Flyway"  --> Postgres
    Spring  -- "S3 SDK"        --> MinIO
    Spring  -- "AMQP publish"  --> Rabbit
    Spring  -- "AMQP consume"  --> Rabbit

    Rabbit  -- "consume tasks" --> ML
    ML      -- "boto3 download" --> MinIO
    ML      -- "publish result" --> Rabbit
```

---

## 2. Sequence diagram — загрузка и классификация фотографии

Полный сценарий от клика "Upload" до отображения тегов в галерее.

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant FE  as React SPA
    participant BE  as Spring Backend
    participant DB  as PostgreSQL
    participant S3  as MinIO
    participant MQ  as RabbitMQ
    participant ML  as FastAPI ML

    User ->> FE: select file & click Analyze
    FE   ->> BE: POST /api/photos (multipart, JWT)
    BE   ->> BE: validate MIME, size, owner
    BE   ->> S3: putObject(user-X/uuid.jpg)
    S3   -->> BE: 200 OK
    BE   ->> DB: INSERT photo (status=PENDING)
    DB   -->> BE: id=42
    BE   ->> MQ: publish task {photoId:42, s3Key, bucket}
    BE   -->> FE: 200 OK { id:42, status:PENDING }
    FE   -->> User: photo card with PENDING dot

    Note over MQ,ML: async — независимая обработка

    MQ   ->> ML: deliver task
    ML   ->> S3: getObject(s3Key)
    S3   -->> ML: image bytes
    ML   ->> ML: preprocess + EfficientNet-B0 forward
    ML   ->> MQ: publish result {photoId:42, status:OK, styles:[...]}
    ML   ->> MQ: ack task

    MQ   ->> BE: deliver result
    BE   ->> DB: BEGIN tx
    BE   ->> DB: DELETE FROM photo_styles WHERE photo_id=42
    BE   ->> DB: INSERT photo_styles (3 строки)
    BE   ->> DB: UPDATE photos SET status='DONE'
    BE   ->> DB: COMMIT

    Note over FE: poll каждые 3s пока есть PENDING
    FE   ->> BE: GET /api/photos
    BE   ->> DB: SELECT photos + styles
    DB   -->> BE: photo 42 status=DONE, styles=[...]
    BE   -->> FE: 200 OK with tags
    FE   -->> User: dot turns green, теги появились
```

---

## 3. Class diagram — модель домена

Сущности JPA и их связи.

```mermaid
classDiagram
    class User {
        +Long id
        +String email
        +String password
        +Instant createdAt
    }

    class Photo {
        +Long id
        +String s3Key
        +Instant uploadedAt
        +PhotoStatus status
    }

    class PhotoStatus {
        <<enum>>
        PENDING
        DONE
        FAILED
    }

    class Style {
        +Long id
        +String name
    }

    class PhotoStyle {
        +PhotoStyleId id
        +double confidence
    }

    class PhotoStyleId {
        <<embeddable>>
        +Long photoId
        +Long styleId
    }

    User "1" --> "*" Photo : owns
    Photo --> PhotoStatus
    Photo "1" --> "*" PhotoStyle : tagged with
    Style "1" --> "*" PhotoStyle : applied to
    PhotoStyle --> PhotoStyleId
```

---

## 4. State diagram — жизненный цикл фотографии

```mermaid
stateDiagram-v2
    [*] --> PENDING : POST /api/photos<br/>файл сохранён,<br/>задача опубликована

    PENDING --> DONE : result OK<br/>теги записаны
    PENDING --> FAILED : result ERROR<br/>или таймаут ML

    FAILED --> PENDING : повторная классификация<br/>(будущая фича)

    DONE --> [*] : DELETE /api/photos/{id}
    FAILED --> [*] : DELETE /api/photos/{id}
    PENDING --> [*] : DELETE /api/photos/{id}
```

---

## 5. Use case diagram

```mermaid
flowchart TB
    User((User))
    System[Visual Style Classifier]

    subgraph Auth
        UC1[Register]
        UC2[Log in]
        UC3[Log out]
    end

    subgraph Photos
        UC4[Upload one or more photos]
        UC5[View gallery]
        UC6[Open photo with style analysis]
        UC7[Find similar photos]
        UC8[Filter gallery by style]
        UC9[Delete photo]
    end

    subgraph Profile
        UC10[View own statistics]
    end

    User --> UC1
    User --> UC2
    User --> UC3
    User --> UC4
    User --> UC5
    User --> UC6
    User --> UC7
    User --> UC8
    User --> UC9
    User --> UC10

    UC1 -.-> System
    UC2 -.-> System
    UC4 -.-> System
    UC5 -.-> System
    UC6 -.-> System
    UC7 -.-> System
    UC8 -.-> System
    UC9 -.-> System
    UC10 -.-> System
```

---

## 6. Deployment diagram

```mermaid
flowchart TB
    subgraph DevMachine[Developer machine / Demo host]
        subgraph DockerNet[Docker network: psc-network]
            backendC[Container: psc-backend<br/>Spring Boot]
            mlC[Container: psc-ml<br/>FastAPI + PyTorch]
            pgC[(Container: psc-postgres)]
            mqC{{Container: psc-rabbitmq}}
            minioC[(Container: psc-minio)]
        end
        viteC[Local Vite dev server<br/>:5173]
    end
    browser([Browser])

    browser --> viteC
    viteC --> backendC
    browser --> minioC

    backendC --> pgC
    backendC --> mqC
    backendC --> minioC
    mlC --> mqC
    mlC --> minioC
```
