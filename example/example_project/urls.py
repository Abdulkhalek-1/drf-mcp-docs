from books.views import AuthorViewSet, BookViewSet
from django.urls import include, path
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"authors", AuthorViewSet)
router.register(r"books", BookViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
]
