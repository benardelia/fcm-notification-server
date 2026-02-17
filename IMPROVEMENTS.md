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

**Gaps identified:**

- Firebase credentials hardcoded and committed to repo
- Notify endpoint uses GET with hardcoded message content
- No async processing (notifications sent synchronously)
- SQLite database (not production-ready)
- No API versioning, rate limiting, or documentation
- No containerization or CI/CD
- Empty test suite
- DEBUG=True with exposed SECRET_KEY

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

- [ ] Move `SECRET_KEY` to environment variable
- [ ] Move Firebase credential paths to environment variable (`GOOGLE_APPLICATION_CREDENTIALS`)
- [ ] Add `.json` credential files to `.gitignore`
- [ ] Set `DEBUG = False` in production settings
- [ ] Configure `ALLOWED_HOSTS` properly

### Authentication & Authorization

- [ ] Add token expiry dates to `ApiClient` model
- [ ] Implement automatic token rotation
- [ ] Add IP whitelisting option for API clients
- [ ] Add request signing (HMAC) verification for webhook callbacks
- [ ] Add per-client permission scopes (e.g., send-only, read-only, admin)

### Rate Limiting

- [ ] Add DRF throttling classes per API client
- [ ] Configure different rate limits per endpoint:
  - Send notification: 100/minute
  - Bulk send: 10/minute
  - Device registration: 50/minute
  - Analytics: 30/minute

### CORS & Headers

- [ ] Install and configure `django-cors-headers`
- [ ] Add security headers (HSTS, X-Content-Type-Options, X-Frame-Options)
- [ ] Configure CSRF protection for browser-based access

### Data Protection

- [ ] Encrypt sensitive fields at rest (push tokens, API tokens)
- [ ] Add audit logging for all API client actions
- [ ] Implement soft-delete for profiles and devices
- [ ] Add data retention policies (auto-cleanup old delivery logs)

---

## 4. Functional Requirements to Add

### Notification Features

| Feature | Description | Priority |
|---|---|---|
| **Dynamic Content** | Accept title, body, data from API request instead of hardcoding | High |
| **Scheduled Notifications** | Send at a future time using Celery Beat | High |
| **Template System** | Reusable notification templates with `{{variable}}` substitution | High |
| **Bulk Send** | Send to multiple devices/phone numbers in one API call | High |
| **Silent/Data Notifications** | Support data-only pushes for background app updates | Medium |
| **Rich Notifications** | Support images, action buttons, and deep links | Medium |
| **Notification Channels** | Android notification channel configuration | Medium |
| **Priority Levels** | High/normal priority with different TTL and handling | Medium |
| **Notification Grouping** | Collapse key support to group similar notifications on device | Medium |
| **Recurring Notifications** | Cron-style repeating notifications | Low |

### Device Management

| Feature | Description | Priority |
|---|---|---|
| **Token Validation** | Validate FCM tokens on registration | High |
| **Stale Token Cleanup** | Auto-deactivate tokens that FCM reports as invalid | High |
| **Device Metadata** | Track OS version, device model, timezone | Medium |
| **Multi-device Support** | Proper handling when user has multiple devices | Medium |

### User Segmentation

| Feature | Description | Priority |
|---|---|---|
| **Filter by Platform** | Send only to iOS, Android, or Web devices | High |
| **Filter by App Version** | Target specific app versions | Medium |
| **Filter by Last Seen** | Target active users within a time window | Medium |
| **Custom Tags** | Tag devices with custom labels for targeting | Low |

### Integration Features

| Feature | Description | Priority |
|---|---|---|
| **Webhook Callbacks** | Notify consuming apps on delivery/read/failure events | High |
| **Retry with Backoff** | Auto-retry failed notifications with exponential backoff | High |
| **Delivery Reports** | Batch delivery status API for polling | Medium |
| **Event Streaming** | WebSocket endpoint for real-time delivery events | Low |

---

## 5. Non-Functional Requirements

### Performance

| Requirement | Implementation |
|---|---|
| **Async Processing** | Celery + Redis for background notification sending |
| **Connection Pooling** | Database connection pooling with `django-db-connection-pool` |
| **Caching** | Redis cache for device token lookups and rate limit counters |
| **Batch Operations** | Process bulk sends in chunks of 500 (FCM limit) |
| **Target Throughput** | Handle 1000+ notifications/minute |

### Reliability

| Requirement | Implementation |
|---|---|
| **Database** | Switch from SQLite to PostgreSQL |
| **Message Queue** | Redis or RabbitMQ as Celery broker |
| **Idempotency** | Idempotency keys to prevent duplicate sends on retry |
| **Dead Letter Queue** | Store permanently failed notifications for review |
| **Health Checks** | `/health/` endpoint checking DB, Redis, and Firebase connectivity |
| **Graceful Degradation** | Queue notifications if Firebase is temporarily unreachable |

### Observability

| Requirement | Implementation |
|---|---|
| **Structured Logging** | JSON-formatted logs with `django-structlog` |
| **Error Tracking** | Sentry integration for exception monitoring |
| **Metrics** | Prometheus metrics (sent/delivered/failed counters, latency histograms) |
| **Request Tracing** | Correlation IDs across API requests and Celery tasks |
| **Analytics Dashboard** | Daily/weekly/monthly sent/delivered/read/failed aggregations |

### Deployment

| Requirement | Implementation |
|---|---|
| **Containerization** | Dockerfile + docker-compose (Django, Celery, Redis, PostgreSQL) |
| **Environment Config** | `.env` file with `django-environ` |
| **CI/CD Pipeline** | GitHub Actions for lint, test, build, deploy |
| **Database Migrations** | Automated migration running on deploy |
| **Secrets Management** | Docker secrets or cloud provider secret manager |

### API Quality

| Requirement | Implementation |
|---|---|
| **Documentation** | Auto-generated Swagger/OpenAPI via `drf-spectacular` |
| **Versioning** | URL-based versioning (`/api/v1/`, `/api/v2/`) |
| **Pagination** | Cursor-based pagination for large result sets |
| **Filtering** | `django-filter` for querystring filtering on list endpoints |
| **Error Responses** | Consistent error response format with error codes |

### Testing

| Requirement | Implementation |
|---|---|
| **Unit Tests** | Test models, serializers, services in isolation |
| **Integration Tests** | Test API endpoints with mocked Firebase |
| **Factory Pattern** | Use `factory_boy` for test data generation |
| **Coverage Target** | Minimum 80% code coverage |
| **Load Testing** | Locust scripts for performance benchmarking |

---

## 6. Target Project Structure

```
fcm_server/
├── docker-compose.yml               # Docker services (Django, Celery, Redis, PostgreSQL)
├── Dockerfile                       # Application container
├── requirements/
│   ├── base.txt                     # Shared dependencies
│   ├── development.txt              # Dev tools (debug toolbar, factory_boy)
│   └── production.txt               # Production deps (gunicorn, sentry-sdk)
├── .env.example                     # Environment variable template
├── .gitignore                       # Ignore credentials, venv, db, .env
├── manage.py
│
├── fcm_server/                      # Project configuration
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                  # Shared settings
│   │   ├── development.py           # Dev overrides (DEBUG=True, SQLite)
│   │   └── production.py            # Production (PostgreSQL, security)
│   ├── celery.py                    # Celery application config
│   ├── urls.py                      # Root URL config
│   ├── wsgi.py
│   └── asgi.py
│
├── notification/                    # Core notification app
│   ├── models/
│   │   ├── __init__.py              # Import all models
│   │   ├── profile.py               # Profile model
│   │   ├── device.py                # Device model
│   │   ├── notification.py          # Notification + DeliveryLog models
│   │   ├── topic.py                 # Topic + UserTopic models
│   │   ├── template.py              # NotificationTemplate model
│   │   ├── api_client.py            # ApiClient model
│   │   └── webhook.py               # WebhookEndpoint model
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── urls.py              # v1 URL patterns
│   │       ├── views/
│   │       │   ├── __init__.py
│   │       │   ├── notify.py        # Send notification views
│   │       │   ├── device.py        # Device CRUD views
│   │       │   ├── profile.py       # Profile CRUD views
│   │       │   ├── topic.py         # Topic management views
│   │       │   ├── template.py      # Template CRUD views
│   │       │   ├── analytics.py     # Analytics views
│   │       │   └── health.py        # Health check view
│   │       └── serializers/
│   │           ├── __init__.py
│   │           ├── notify.py
│   │           ├── device.py
│   │           ├── profile.py
│   │           ├── topic.py
│   │           └── template.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── fcm_service.py           # Firebase messaging wrapper
│   │   ├── token_manager.py         # Token validation and cleanup
│   │   ├── template_engine.py       # Template variable substitution
│   │   ├── webhook_dispatcher.py    # Webhook event delivery
│   │   └── analytics_service.py     # Analytics aggregation
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── send_notification.py     # Async send tasks
│   │   ├── cleanup.py               # Token cleanup, log retention
│   │   ├── analytics.py             # Daily analytics aggregation
│   │   └── webhooks.py              # Webhook delivery tasks
│   ├── middleware.py                # Authentication middleware
│   ├── permissions.py               # Custom permission classes
│   ├── throttling.py                # Rate limiting classes
│   ├── signals.py                   # Django signals (post-send events)
│   ├── exceptions.py                # Custom exception classes
│   ├── admin.py
│   ├── apps.py
│   └── tests/
│       ├── __init__.py
│       ├── factories.py             # factory_boy factories
│       ├── test_models.py
│       ├── test_views.py
│       ├── test_fcm_service.py
│       ├── test_tasks.py
│       └── test_serializers.py
│
├── analytics/                       # Analytics app (optional, separate)
│   ├── models.py                    # NotificationAnalytics model
│   ├── views.py                     # Dashboard API views
│   └── tasks.py                     # Aggregation tasks
│
└── sdk/                             # Python client SDK
    ├── fcm_client/
    │   ├── __init__.py
    │   ├── client.py                # HTTP client wrapper
    │   ├── exceptions.py
    │   └── models.py                # Response models
    ├── setup.py
    └── README.md
```

---

## 7. Key New Models to Add

### NotificationTemplate

```python
class NotificationTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    title_template = models.CharField(max_length=255)
    body_template = models.TextField()
    default_data = models.JSONField(default=dict, blank=True)
    platform_overrides = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(ApiClient, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Usage example:**
```python
# Template: "Hello {{name}}, your order #{{order_id}} is {{status}}"
# Variables: {"name": "John", "order_id": "1234", "status": "ready"}
# Result:   "Hello John, your order #1234 is ready"
```

### ScheduledNotification

```python
class ScheduledNotification(models.Model):
    REPEAT_CHOICES = [
        ('none', 'No Repeat'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    scheduled_at = models.DateTimeField()
    repeat_interval = models.CharField(max_length=10, choices=REPEAT_CHOICES, default='none')
    is_recurring = models.BooleanField(default=False)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    max_occurrences = models.IntegerField(null=True, blank=True)
    occurrence_count = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
```

### NotificationAnalytics

```python
class NotificationAnalytics(models.Model):
    date = models.DateField()
    api_client = models.ForeignKey(ApiClient, on_delete=models.CASCADE, null=True)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    platform = models.CharField(max_length=10, blank=True)
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_read = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    avg_delivery_time_ms = models.IntegerField(null=True)

    class Meta:
        unique_together = ('date', 'api_client', 'topic', 'platform')
```

### WebhookEndpoint

```python
class WebhookEndpoint(models.Model):
    EVENT_CHOICES = [
        ('notification.sent', 'Notification Sent'),
        ('notification.delivered', 'Notification Delivered'),
        ('notification.read', 'Notification Read'),
        ('notification.failed', 'Notification Failed'),
        ('device.registered', 'Device Registered'),
        ('device.deactivated', 'Device Deactivated'),
    ]

    api_client = models.ForeignKey(ApiClient, on_delete=models.CASCADE)
    url = models.URLField()
    events = models.JSONField(default=list)  # List of event types to subscribe to
    secret_key = models.CharField(max_length=255)  # For HMAC signature verification
    is_active = models.BooleanField(default=True)
    failure_count = models.IntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 8. Priority Implementation Order

### Phase 1 - Security & Foundation (Week 1)

- [x] ~~Current: Basic API with hardcoded Firebase~~
- [ ] Move secrets to environment variables (`django-environ`)
- [ ] Add `.gitignore` for credentials and `.env`
- [ ] Create `.env.example` template
- [ ] Split settings into `base.py`, `development.py`, `production.py`
- [ ] Fix notify endpoint: POST method, accept dynamic content

### Phase 2 - Production Infrastructure (Week 2)

- [ ] Switch to PostgreSQL
- [ ] Set up Celery + Redis for async processing
- [ ] Create `Dockerfile` and `docker-compose.yml`
- [ ] Add health check endpoint
- [ ] Create `requirements/base.txt`, `development.txt`, `production.txt`

### Phase 3 - API Redesign (Week 3)

- [ ] Add API versioning (`/api/v1/`)
- [ ] Implement bulk send endpoint
- [ ] Implement topic notification endpoint
- [ ] Add proper error response format
- [ ] Set up `drf-spectacular` for Swagger documentation
- [ ] Add cursor-based pagination
- [ ] Add `django-filter` for list filtering

### Phase 4 - Core Features (Week 4)

- [ ] Build notification template system
- [ ] Add scheduled notifications with Celery Beat
- [ ] Implement stale token cleanup service
- [ ] Add retry logic with exponential backoff
- [ ] Support rich notifications (images, actions, deep links)
- [ ] Add silent/data-only notification support

### Phase 5 - Security & Auth (Week 5)

- [ ] Add API client token expiry and rotation
- [ ] Implement per-client permission scopes
- [ ] Add DRF throttling (rate limiting)
- [ ] Configure `django-cors-headers`
- [ ] Add IP whitelisting option
- [ ] Implement idempotency key support
- [ ] Add audit logging

### Phase 6 - Integrations (Week 6)

- [ ] Build webhook system (model, dispatcher, delivery tasks)
- [ ] Add HMAC signature verification for webhooks
- [ ] Implement delivery report polling API
- [ ] Build user segmentation filters (platform, version, last seen)

### Phase 7 - Observability (Week 7)

- [ ] Set up structured logging with `django-structlog`
- [ ] Integrate Sentry for error tracking
- [ ] Add Prometheus metrics endpoint
- [ ] Build analytics aggregation (daily task)
- [ ] Create analytics API endpoints

### Phase 8 - Testing & CI/CD (Week 8)

- [ ] Write unit tests for models and services
- [ ] Write integration tests for API endpoints
- [ ] Set up `factory_boy` for test data
- [ ] Configure GitHub Actions CI pipeline
- [ ] Add pre-commit hooks (linting, formatting)
- [ ] Create Locust load testing scripts

### Phase 9 - Developer Experience (Week 9)

- [ ] Build Python client SDK (`pip install fcm-server-client`)
- [ ] Write SDK documentation
- [ ] Create example integration projects
- [ ] Write deployment guide

---

## Dependencies to Add

```txt
# requirements/base.txt
Django>=5.2
djangorestframework>=3.16
firebase-admin>=6.8
django-environ>=0.12
celery>=5.4
redis>=5.0
django-cors-headers>=4.4
drf-spectacular>=0.28
django-filter>=24.3
psycopg2-binary>=2.9

# requirements/development.txt
-r base.txt
factory-boy>=3.3
pytest-django>=4.8
pytest-cov>=5.0
django-debug-toolbar>=4.4

# requirements/production.txt
-r base.txt
gunicorn>=22.0
sentry-sdk>=2.10
django-structlog>=8.0
django-prometheus>=2.3
whitenoise>=6.7
```

---

## Docker Compose Target

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis
    volumes:
      - .:/app

  celery_worker:
    build: .
    command: celery -A fcm_server worker -l info
    env_file: .env
    depends_on:
      - db
      - redis

  celery_beat:
    build: .
    command: celery -A fcm_server beat -l info
    env_file: .env
    depends_on:
      - db
      - redis

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: fcm_server
      POSTGRES_USER: fcm_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```
