from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=300)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    isbn = models.CharField(max_length=13, unique=True)
    published_date = models.DateField()
    page_count = models.PositiveIntegerField(default=0)
    in_stock = models.BooleanField(default=True)

    def __str__(self):
        return self.title
