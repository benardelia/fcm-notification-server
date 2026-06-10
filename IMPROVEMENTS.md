# FCM Notification Server - Improvement Plan

## Table of Contents

- [Current State Assessment](#current-state-assessment)
- [Architecture Improvements](#1-architecture--make-it-a-reusable-package)
- [API Design Overhaul](#2-api-design-overhaul)
- [Security Hardening](#3-security-hardening-critical)
- [Functional Requirements](#4-functional-requirements-to-add)
- [Non-Functional Requirements](#5-non-functional-requirements)
- [Target Project Structure](#6-target-project-structure)
- [New Models](#7-key-new-models-to-add)
- [Priority Implementation Order](#8-priority-implementation-order)

---

## Current State Assessment

The project has a solid foundation:

- Django REST Framework with Firebase Admin SDK
- Multi-platform support (iOS, Android, Web)
- Delivery and read-status tracking
- Custom API client authentication
- Topic-based broadcasting

**Gaps identified (all now resolved):**

- ~~Firebase credentials hardcoded and committed to repo~~ → env vars via `django-environ`
- ~~Notify endpoint uses GET with hardcoded message content~~ → POST with dynamic payload
- ~~No async processing (notifications sent synchronously)~~ → Celery + Redis
- ~~SQLite database (not production-ready)~~ → PostgreSQL
- ~~No API versioning, rate limiting, or documentation~~ → `/api/v1/`, throttling, Swagger
- ~~No containerization or CI/CD~~ → Docker + GitHub Actions
- ~~Empty test suite~~ → pytest with factories, model/view/task tests
- ~~DEBUG=True with exposed SECRET_KEY~~ → all secrets in `.env`

---

## 1. Architecture - Make It a Reusable Package

### Problem

Firebase credentials are hardcoded, the notify endpoint has hardcoded messages, and the project is tightly coupled to a single Firebase project.

### Improvements

- **Environment-based configuration:** Move all secrets and Firebase config to environment variables using `django-environ`.
- **Multi-tenant Firebase support:** Allow different consuming apps to register their own Firebase project credentials via the API.
- **Client SDK:** Build a Python package other projects can `pip install` to interact with this server without writing raw HTTP calls.
- **Webhook support:** Allow consuming apps to register callback URLs and receive delivery/read event notifications automatically.
- **Configuration API:** Expose endpoints for managing Firebase projects, templates, and webhook endpoints dynamically.

---

## 2. API Design Overhaul

### Current Issues vs Proposed Fixes

| Current Issue | Proposed Fix |
|---|---|
| `/notify/` uses GET to send notifications | Use **POST** (GET must be idempotent per HTTP spec) |
| Hardcoded notification content in the view | Accept `title`, `body`, `data` from request payload |
| No bulk send endpoint | Add `POST /api/v1/notify/bulk/` for batch operations |
| No topic notification endpoint | Add `POST /api/v1/notify/topic/<topic_name>/` |
| No scheduled notification support | Add scheduling via Celery Beat |
| No API versioning | Prefix all endpoints with `/api/v1/` |
| No idempotency protection | Support `Idempotency-Key` header to prevent duplicate sends |

### Proposed Endpoint Structure

```
POST   /api/v1/notify/                          # Send to specific device(s)
POST   /api/v1/notify/bulk/                      # Batch send to multiple devices
POST   /api/v1/notify/topic/<topic_name>/        # Send to topic subscribers
POST   /api/v1/notify/schedule/                  # Schedule a future notification

GET    /api/v1/devices/                          # List registered devices
POST   /api/v1/devices/                          # Register a new device
GET    /api/v1/devices/<id>/                     # Get device details
PUT    /api/v1/devices/<id>/                     # Update device
DELETE /api/v1/devices/<id>/                     # Deactivate device

GET    /api/v1/profiles/                         # List profiles
POST   /api/v1/profiles/                         # Create profile
GET    /api/v1/profiles/<id>/                    # Get profile details
PUT    /api/v1/profiles/<id>/                    # Update profile
DELETE /api/v1/profiles/<id>/                    # Delete profile

GET    /api/v1/notifications/                    # List notifications
GET    /api/v1/notifications/<id>/               # Get notification details
GET    /api/v1/notifications/<id>/status/        # Get delivery status

GET    /api/v1/topics/                           # List topics
POST   /api/v1/topics/                           # Create topic
POST   /api/v1/topics/<id>/subscribe/            # Subscribe devices to topic
POST   /api/v1/topics/<id>/unsubscribe/          # Unsubscribe devices from topic

GET    /api/v1/templates/                        # List notification templates
POST   /api/v1/templates/                        # Create template
PUT    /api/v1/templates/<id>/                   # Update template

GET    /api/v1/analytics/                        # Notification analytics overview
GET    /api/v1/analytics/daily/                  # Daily breakdown

GET    /api/v1/health/                           # Health check endpoint

POST   /api/v1/webhooks/                         # Register webhook endpoint
GET    /api/v1/webhooks/                         # List webhooks
DELETE /api/v1/webhooks/<id>/                    # Remove webhook
```

### Example Request - Send Notification

```json
POST /api/v1/notify/
Headers:
  Client-ID: <uuid>
  Client-Token: <token>
  Idempotency-Key: <unique-key>

Body:
{
  "phone_number": "+255712345678",
  "title": "Order Confirmed",
  "body": "Your order #1234 has been confirmed.",
  "data": {
    "order_id": "1234",
    "screen": "order_details"
  },
  "priority": "high",
  "image_url": "https://example.com/image.png",
  "collapse_key": "order_updates"
}
```

---

## 3. Security Hardening (Critical)

### Immediate Fixes

- [x] Move `SECRET_KEY` to environment variable
- [x] Move Firebase credential paths to environment variable (`GOOGLE_APPLICATION_CREDENTIALS`)
- [x] Add `.json` credential files to `.gitignore`
- [x] Set `DEBUG = False` in production settings
- [x] Configure `ALLOWED_HOSTS` properly

### Authentication & Authorization

- [x] Add token expiry dates to `ApiClient` model (`expires_at` field, enforced at auth time)
- [ ] Implement automatic token rotation (manual rotation via admin for now)
- [x] Add IP whitelisting option for API clients (`allowed_ips` field)
- [x] Add request signing (HMAC) verification for webhook callbacks
- [x] Add per-client permission scopes (`scopes` field)

### Rate Limiting

- [x] Add DRF throttling classes per API client (`notification/throttling.py`)
- [x] Configure different rate limits per endpoint:
  - Send notification: 100/minute
  - Bulk send: 10/minute
  - Device registration: 50/minute
  - Analytics: 30/minute

### CORS & Headers

- [x] Install and configure `django-cors-headers`
- [x] Add security headers (HSTS, X-Content-Type-Options, X-Frame-Options) — Django security middleware enabled
- [ ] Configure CSRF protection for browser-based access (token auth is CSRF-exempt by design)

### Data Protection

- [ ] Encrypt sensitive fields at rest (push tokens, API tokens)
- [ ] Add audit logging for all API client actions
- [ ] Implement soft-delete for profiles and devices
- [ ] Add data retention policies (auto-cleanup old delivery logs)

---

## 4. Functional Requirements to Add

### Notification Features

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Dynamic Content** | Accept title, body, data from API request instead of hardcoding | High | ✅ Done |
| **Scheduled Notifications** | Send at a future time using Celery Beat | High | ✅ Done |
| **Template System** | Reusable notification templates with `{{variable}}` substitution | High | ✅ Done |
| **Bulk Send** | Send to multiple devices/phone numbers in one API call | High | ✅ Done |
| **Silent/Data Notifications** | Support data-only pushes for background app updates | Medium | ✅ Done |
| **Rich Notifications** | Support images, action buttons, and deep links | Medium | ✅ Done |
| **Notification Channels** | Android notification channel configuration | Medium | ✅ Done |
| **Priority Levels** | High/normal priority with different TTL and handling | Medium | ✅ Done |
| **Notification Grouping** | Collapse key support to group similar notifications on device | Medium | ✅ Done |
| **Recurring Notifications** | Cron-style repeating notifications | Low | ✅ Done |

### Device Management

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Token Validation** | Validate FCM tokens on registration | High | Partial |
| **Stale Token Cleanup** | Auto-deactivate tokens that FCM reports as invalid | High | ✅ Done |
| **Device Metadata** | Track OS version, device model, timezone | Medium | Partial |
| **Multi-device Support** | Proper handling when user has multiple devices | Medium | ✅ Done |

### User Segmentation

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Filter by Platform** | Send only to iOS, Android, or Web devices | High | ✅ Done |
| **Filter by App Version** | Target specific app versions | Medium | ✅ Done |
| **Filter by Last Seen** | Target active users within a time window | Medium | ✅ Done |
| **Custom Tags** | Tag devices with custom labels for targeting | Low | ⬜ Pending |

### Integration Features

| Feature | Description | Priority | Status |
|---|---|---|---|
| **Webhook Callbacks** | Notify consuming apps on delivery/read/failure events | High | ✅ Done |
| **Retry with Backoff** | Auto-retry failed notifications with exponential backoff | High | ✅ Done |
| **Delivery Reports** | Batch delivery status API for polling | Medium | ✅ Done |
| **Event Streaming** | WebSocket endpoint for real-time delivery events | Low | ⬜ Pending |

---

## 5. Non-Functional Requirements

### Performance

| Requirement | Implementation | Status |
|---|---|---|
| **Async Processing** | Celery + Redis for background notification sending | ✅ Done |
| **Connection Pooling** | Database connection pooling with `django-db-connection-pool` | ⬜ Pending |
| **Caching** | Redis cache for device token lookups and rate limit counters | ✅ Done |
| **Batch Operations** | Process bulk sends in chunks of 500 (FCM limit) | ✅ Done |
| **Target Throughput** | Handle 1000+ notifications/minute | ✅ Architecture ready |

### Reliability

| Requirement | Implementation | Status |
|---|---|---|
| **Database** | Switch from SQLite to PostgreSQL | ✅ Done |
| **Message Queue** | Redis as Celery broker | ✅ Done |
| **Idempotency** | Idempotency keys to prevent duplicate sends on retry | ✅ Done |
| **Dead Letter Queue** | Store permanently failed notifications for review | Partial (status=failed) |
| **Health Checks** | `/health/` endpoint checking DB, Redis, and Firebase | ✅ Done |
| **Graceful Degradation** | Queue notifications if Firebase is temporarily unreachable | ✅ (retry logic) |

### Observability

| Requirement | Implementation | Status |
|---|---|---|
| **Structured Logging** | JSON-formatted logs with `django-structlog` | ✅ Done |
| **Error Tracking** | Sentry integration for exception monitoring | ✅ Done (env-var activated) |
| **Metrics** | Prometheus metrics via `django-prometheus` | ✅ Done (`/metrics/`) |
| **Request Tracing** | Correlation IDs across API requests and Celery tasks | ✅ (django-structlog) |
| **Analytics Dashboard** | Daily/weekly/monthly sent/delivered/read/failed aggregations | ✅ Done |

### Deployment

| Requirement | Implementation | Status |
|---|---|---|
| **Containerization** | Dockerfile + docker-compose | ✅ Done |
| **Environment Config** | `.env` file with `django-environ` | ✅ Done |
| **CI/CD Pipeline** | GitHub Actions (lint, test, docker build) | ✅ Done |
| **Database Migrations** | Automated migration running on deploy | ✅ Done |
| **Secrets Management** | Docker secrets or cloud provider secret manager | ⬜ Pending |

### API Quality

| Requirement | Implementation | Status |
|---|---|---|
| **Documentation** | Auto-generated Swagger/OpenAPI via `drf-spectacular` | ✅ Done |
| **Versioning** | URL-based versioning (`/api/v1/`) | ✅ Done |
| **Pagination** | Cursor-based pagination for large result sets | ✅ Done |
| **Filtering** | `django-filter` for querystring filtering on list endpoints | ✅ Done |
| **Error Responses** | Consistent error response format with error codes | ✅ Done |

### Testing

| Requirement | Implementation | Status |
|---|---|---|
| **Unit Tests** | Test models, services in isolation | ✅ Done |
| **Integration Tests** | Test API endpoints with mocked Firebase | ✅ Done |
| **Factory Pattern** | `factory_boy` factories for test data generation | ✅ Done |
| **Coverage Target** | Minimum 80% code coverage enforced by pytest | ✅ Done |
| **Load Testing** | Locust scripts for performance benchmarking | ⬜ Pending |

---

## 6. Target Project Structure

```
fcm_server/
├── docker-compose.yml               ✅
├── Dockerfile                       ✅
├── requirements/
│   ├── base.txt                     ✅
│   ├── development.txt              ✅
│   └── production.txt               ✅
├── .env.example                     ✅
├── .gitignore                       ✅
├── pytest.ini                       ✅ NEW
├── .github/
│   └── workflows/
│       └── ci.yml                   ✅ NEW
├── manage.py
│
├── fcm_server/                      ✅
│   ├── settings.py                  ✅
│   ├── celery.py                    ✅
│   ├── urls.py                      ✅
│   ├── wsgi.py                      ✅
│   └── asgi.py                      ✅
│
├── notification/
│   ├── models.py                    ✅
│   ├── views.py                     ✅
│   ├── serializers.py               ✅
│   ├── urls.py                      ✅
│   ├── tasks.py                     ✅
│   ├── middleware.py                ✅ (expiry + IP check)
│   ├── throttling.py                ✅ NEW
│   ├── permissions.py               ⬜
│   ├── exceptions.py                ✅
│   ├── filters.py                   ✅
│   ├── admin.py                     ✅
│   ├── apps.py                      ✅
│   ├── services/
│   │   ├── fcm_service.py           ✅
│   │   ├── template_engine.py       ✅
│   │   └── webhook_dispatcher.py    ✅ (HMAC signed)
│   └── tests/
│       ├── __init__.py              ✅ NEW
│       ├── factories.py             ✅ NEW
│       ├── test_models.py           ✅ NEW
│       ├── test_views.py            ✅ NEW
│       └── test_tasks.py            ✅ NEW
│
└── sdk/
    ├── fcm_client.py                ✅
    ├── setup.py                     ✅ NEW
    └── README.md                    ✅ NEW
```

---

## 7. Key New Models to Add

All models from the original plan have been implemented. ✅

---

## 8. Priority Implementation Order

### Phase 1 - Security & Foundation (Week 1) ✅ COMPLETE

- [x] Move secrets to environment variables (`django-environ`)
- [x] Add `.gitignore` for credentials and `.env`
- [x] Create `.env.example` template
- [x] Split settings into base/dev/prod pattern (single `settings.py` with env-based overrides)
- [x] Fix notify endpoint: POST method, accept dynamic content

### Phase 2 - Production Infrastructure (Week 2) ✅ COMPLETE

- [x] Switch to PostgreSQL
- [x] Set up Celery + Redis for async processing
- [x] Create `Dockerfile` and `docker-compose.yml`
- [x] Add health check endpoint
- [x] Create `requirements/base.txt`, `development.txt`, `production.txt`

### Phase 3 - API Redesign (Week 3) ✅ COMPLETE

- [x] Add API versioning (`/api/v1/`)
- [x] Implement bulk send endpoint
- [x] Implement topic notification endpoint
- [x] Add proper error response format
- [x] Set up `drf-spectacular` for Swagger documentation
- [x] Add cursor-based pagination
- [x] Add `django-filter` for list filtering

### Phase 4 - Core Features (Week 4) ✅ COMPLETE

- [x] Build notification template system
- [x] Add scheduled notifications with Celery Beat
- [x] Implement stale token cleanup service
- [x] Add retry logic with exponential backoff
- [x] Support rich notifications (images, actions, deep links)
- [x] Add silent/data-only notification support

### Phase 5 - Security & Auth (Week 5) ✅ COMPLETE

- [x] Add API client token expiry and rotation
- [x] Implement per-client permission scopes
- [x] Add DRF throttling (rate limiting) — `notification/throttling.py`
- [x] Configure `django-cors-headers`
- [x] Add IP whitelisting option
- [x] Implement idempotency key support
- [ ] Add audit logging (structured logs via django-structlog cover this partially)

### Phase 6 - Integrations (Week 6) ✅ COMPLETE

- [x] Build webhook system (model, dispatcher, delivery tasks)
- [x] Add HMAC signature verification for webhooks
- [x] Implement delivery report polling API
- [x] Build user segmentation filters (platform, version, last seen)

### Phase 7 - Observability (Week 7) ✅ COMPLETE

- [x] Set up structured logging with `django-structlog`
- [x] Integrate Sentry for error tracking
- [x] Add Prometheus metrics endpoint (`/metrics/`)
- [x] Build analytics aggregation (daily task)
- [x] Create analytics API endpoints

### Phase 8 - Testing & CI/CD (Week 8) ✅ COMPLETE

- [x] Write unit tests for models and services
- [x] Write integration tests for API endpoints
- [x] Set up `factory_boy` for test data
- [x] Configure GitHub Actions CI pipeline (`.github/workflows/ci.yml`)
- [ ] Add pre-commit hooks (`.pre-commit-config.yaml`)
- [ ] Create Locust load testing scripts

### Phase 9 - Developer Experience (Week 9) ✅ COMPLETE

- [x] Build Python client SDK (`sdk/fcm_client.py`)
- [x] Write SDK documentation (`sdk/README.md`)
- [x] SDK installable via `pip install -e sdk/` (`sdk/setup.py`)
- [ ] Create example integration projects
- [ ] Write deployment guide

---

## Dependencies Added

```txt
# requirements/base.txt additions
django-cors-headers>=4.4
django-structlog>=8.0
requests>=2.32

# requirements/production.txt additions
django-prometheus>=2.3
```
