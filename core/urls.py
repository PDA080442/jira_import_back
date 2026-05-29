from django.urls import path

from core.views import HealthLiveView, HealthReadyView

urlpatterns = [
    path("health/", HealthLiveView.as_view(), name="health-live"),
    path("ready/", HealthReadyView.as_view(), name="health-ready"),
]
