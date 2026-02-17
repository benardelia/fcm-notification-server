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