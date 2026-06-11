## Models

Profile → extends Django’s User with phone_number and is_active.

Device → stores iOS/Android/Web device tokens.

Notification → represents a notification you create.

NotificationDeliveryLog → tracks whether each device got/read the notification.

Topic + UserTopic → allow grouping users into broadcast lists.


### Model Relation

    Users → Devices → Notifications → Delivery Logs are linked, with optional Topics for grouping users.



### Flow

User logs into your app → app registers with FCM/APNs → you save the push_token in Devices table.

When you create a notification → save it in Notifications table.

Your server pushes it to FCM/APNs → log result in Delivery Log.

If user taps the notification → app calls your API to update read_at.


## ⚡️ tips:

Always store the raw APNs/FCM tokens per device.

Keep a status log to know who received/read the notification.

Use a data payload (JSON) to navigate users inside the app.


## To run locally (without Docker), create the PostgreSQL database first:


    createdb -U DB_USER notification
    python manage.py migrate
    python manage.py runserver
    And in another terminal for Celery:
.

    celery -A fcm_server worker -l info


## To run using Docker (e.g., for local testing or server deployment):

Make sure Docker and Docker Compose are installed on your machine/server. Then run:

```bash
docker compose up --build -d
```

This command will automatically:
1. Build the necessary Docker images.
2. Apply database migrations.
3. Start the PostgreSQL, Redis, Celery worker, and Celery beat services.
4. Start the Django web server on port `8000` (accessible at `http://localhost:8000`).

**Useful Docker Commands:**
- Stop the containers: `docker compose down`
- View background logs: `docker compose logs -f`
- Access Django shell inside the container: `docker compose exec web python manage.py shell`


## SDK Usage from Other Projects

    from sdk import FCMClient

    client = FCMClient("http://localhost:8000", client_id="...", client_token="...")
    client.send_notification("+255712345678", "Title", "Body", data={"key": "val"})
    client.send_bulk(["+255...", "+255..."], "Title", "Body")
    client.send_to_topic("news", "Breaking", "Details")
    client.create_webhook("https://myapp.com/hook", ["notification.sent"], "my-secret")




## New API Endpoints (all under /notification/)

    POST  notify/              — Send to single device (dynamic content)
    POST  notify/bulk/         — Send to multiple phone numbers
    POST  notify/topic/        — Send to topic subscribers
    CRUD  firebase-projects/   — Manage Firebase credentials per client
    CRUD  templates/           — Notification templates
    CRUD  webhooks/            — Webhook callback endpoints
    GET   analytics/           — Notification analytics
