from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from core.admin import admin_site

urlpatterns = [
    path("admin/", admin_site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/onboarding/", include("onboarding.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/chatbot-admin/", include("chatbot_admin.urls")),
    path("api/cards/", include("cards.urls")),
    path("api/calendar/", include("calendar_entry.urls")),
    path("api/match/", include("match_data.urls")),
    path("api/chatbot-features/", include("chatbot_features.urls")),
    path("api/vision/", include("tracevision.urls"))
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
