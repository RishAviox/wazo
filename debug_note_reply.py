import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wajo_backend.settings_dev')
os.environ.setdefault('DJANGO_DATABASE', 'docker')
django.setup()

from tracevision.views import TraceClipReelNoteViewSet
from accounts.models import WajoUser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()
user = WajoUser.objects.get(id='0b02a749-43a2-4cbe-b4dc-f19ba726f00c') # Amit Shimon
request = factory.post('/api/vision/notes/108/reply/')
request.user = user

view = TraceClipReelNoteViewSet()
view.request = Request(request)
view.action = 'reply'
view.kwargs = {'pk': '108'}

print("--- TESTING get_object() ---")
try:
    obj = view.get_object()
    print(f"Object found: {obj}")
except Exception as e:
    print(f"Exception Type: {type(e)}")
    print(f"Exception Message: {str(e)}")
    # traceback.print_exc()

print("\n--- TESTING reply() ---")
response = view.reply(view.request, pk='108')
print(f"Response Status: {response.status_code}")
print(f"Response Data: {response.data}")
