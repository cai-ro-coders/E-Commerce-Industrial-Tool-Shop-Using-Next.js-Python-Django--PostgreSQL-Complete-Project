from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FileDocumentViewSet, SettingViewSet

router = DefaultRouter()
router.register("settings", SettingViewSet, basename="settings")
router.register("files", FileDocumentViewSet, basename="files")

urlpatterns = [path("", include(router.urls))]
