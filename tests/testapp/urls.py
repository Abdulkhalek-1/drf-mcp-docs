from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tests.testapp.views import CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet)
router.register(r"products", ProductViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
]
