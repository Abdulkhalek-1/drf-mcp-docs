from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from tests.testapp.models import Category, Product
from tests.testapp.serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    """API endpoint for managing categories."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"


class ProductViewSet(viewsets.ModelViewSet):
    """API endpoint for managing products."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    @action(detail=False, methods=["get"])
    def in_stock(self, request):
        """List only products that are in stock."""
        products = self.queryset.filter(in_stock=True)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
