from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from clinic_backend.admin import admin_site

urlpatterns = [
    path("", include("clinic_backend.urls")),
    path("admin/", admin_site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
