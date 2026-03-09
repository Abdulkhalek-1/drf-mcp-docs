from rest_framework import serializers

from books.models import Author, Book


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name", "bio"]


class BookSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "author_name",
            "isbn",
            "published_date",
            "page_count",
            "in_stock",
        ]
