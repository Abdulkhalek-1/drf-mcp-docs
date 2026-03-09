from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from books.models import Author, Book
from books.serializers import AuthorSerializer, BookSerializer


class AuthorViewSet(viewsets.ModelViewSet):
    """API endpoint for managing authors."""

    queryset = Author.objects.all()
    serializer_class = AuthorSerializer


class BookViewSet(viewsets.ModelViewSet):
    """API endpoint for managing books."""

    queryset = Book.objects.all()
    serializer_class = BookSerializer

    @action(detail=False, methods=["get"])
    def in_stock(self, request):
        """List only books that are currently in stock."""
        books = self.queryset.filter(in_stock=True)
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)
