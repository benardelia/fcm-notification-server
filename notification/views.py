from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
import firebase_admin
from firebase_admin import credentials
from rest_framework.views import APIView
from rest_framework.response import Response
from notification.middleware import ApiClientAuthentication
from .serializers import *
from notification.models import Profile
from .cloud_messaging import all_platforms_message, send_to_token, send_multicast
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
# Create your views here.

# cred = credentials.Certificate("vilcom-restaurant-firebase-adminsdk-fbsvc-366d5c2bb6.json")
cred = credentials.Certificate("ardhi-kiganjani-firebase-adminsdk-fbsvc-b5a11c4c3e.json")   # keep these files private never push to the public repositories

# Check if Firebase has already been initialized
if not firebase_admin._apps:
    default_app = firebase_admin.initialize_app(cred)
else:
    default_app = firebase_admin.get_app()

## or you can user this for security / in production
# export GOOGLE_APPLICATION_CREDENTIALS="/path/to/vilcom-restaurant-firebase-adminsdk-fbsvc-366d5c2bb6.json"
## then initialize the app
# default_app = firebase_admin.initialize_app()
# documentation here https://firebase.google.com/docs/cloud-messaging/auth-server
    
class SendNotificationView(APIView):

    def get(self, request):
        try:
            phone_number = request.query_params.get('phone_number')
            if not phone_number:
                return Response(
                    {"error": "Please provide a phone_number parameter."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            profile = get_object_or_404(Profile, phone_number=phone_number)

            device = profile.devices.first()
            if not device:
                return Response(
                    {"error": "No device found for this profile."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            print(f"Sending notification to device with token: {device}")
        
            title = 'Kiwanja Chako'
            body = 'Kiwanja chako chenye namba 127 ilazo, Dodoma. Hati yake iko tayari fika ofisi yetu Dodoma upate. Asante!.'
            data = {"type": "info", "transaction": "GRO"}

            token = device.push_token
            sent_notification = all_platforms_message(token, title=title, body=body, data=data)
            # sent_notification = send_multicast([token], title=title, body=body, data=data)
            notification = Notification.objects.create(
                title=title,
                body=body,
                data_payload=data,
                status="sent",
                scheduled_at=timezone.now(),
                sent_at=timezone.now()
                )

            NotificationDeliveryLog.objects.create(
                notification=notification,
                device=device,
                delivered_at=timezone.now(),
                status="sent",
            )

            print(f"Notification sent successfully: {sent_notification}")

            return Response(
                {
                    "success": True,
                    "message": "Notification sent successfully",
                    "response": str(sent_notification)
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            print(f"Error sending notification: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class ProfileListCreateView(generics.ListCreateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer

class ProfileRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer


class DeviceListCreateView(generics.ListCreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class DeviceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class NotificationListCreateView(generics.ListCreateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

class NotificationRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

class NotificationDeliveryLogListCreateView(generics.ListCreateAPIView):
    queryset = NotificationDeliveryLog.objects.all()
    serializer_class = NotificationDeliveryLogSerializer

class NotificationDeliveryLogRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationDeliveryLog.objects.all()
    serializer_class = NotificationDeliveryLogSerializer

class TopicListCreateView(generics.ListCreateAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class TopicRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class UserTopicListCreateView(generics.ListCreateAPIView):
    queryset = UserTopic.objects.all()
    serializer_class = UserTopicSerializer

class UserTopicRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserTopic.objects.all()
    serializer_class = UserTopicSerializer
    authentication_classes = [ApiClientAuthentication]   # 👈 here
    permission_classes = [IsAuthenticated]               # 👈 requires valid client


# ------------------------------------
# TO add public view just do as below
# ------------------------------------

# ------------------------------------
# from rest_framework.permissions import AllowAny

# class PublicView(generics.ListAPIView):
#     queryset = Something.objects.all()
#     serializer_class = SomethingSerializer
#     permission_classes = [AllowAny]   # No client auth required
