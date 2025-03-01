from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from .models import Category, Product, ProductImage, Review
from apps.accounts.models import User
import tempfile
import os


class ProductsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="user12345",
            first_name="Test",
            last_name="User",
        )

        # Create test admin
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="admin12345",
            first_name="Admin",
            last_name="User",
        )

        # Create category
        self.category = Category.objects.create(
            name="Test Category", description="Test category description"
        )

        # Test product data
        self.product_data = {
            "name": "Test Product",
            "description": "Test product description",
            "category": self.category.id,
            "price": 99.99,
            "stock": 10,
            "is_active": True,
        }

        # Create temp image file for testing
        image = SimpleUploadedFile(
            name="test_image.jpg",
            content=(
                open("apps/products/tests_assets/test_image.jpg", "rb").read()
                if os.path.exists("apps/products/tests_assets/test_image.jpg")
                else b""
            ),
            content_type="image/jpeg",
        )

        # Create product
        self.product = Product.objects.create(
            name="Existing Product",
            description="Existing product description",
            category=self.category,
            price=49.99,
            stock=5,
            is_active=True,
        )

        # Test review data
        self.review_data = {"rating": 4, "comment": "This is a test review"}

    def authenticate_admin(self):
        """Helper method to authenticate as admin"""
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "admin@example.com", "password": "admin12345"},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def authenticate_user(self):
        """Helper method to authenticate as regular user"""
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "user@example.com", "password": "user12345"},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_category_list(self):
        """Test retrieving category list"""
        url = reverse("category-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Test Category")

    def test_create_category(self):
        """Test creating a new category (admin only)"""
        self.authenticate_admin()

        url = reverse("category-list")
        data = {"name": "New Category", "description": "New category description"}

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

        # Test that regular users cannot create categories
        self.client.credentials()  # Clear credentials
        self.authenticate_user()

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_list(self):
        """Test retrieving product list"""
        url = reverse("product-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Existing Product")

    def test_product_detail(self):
        """Test retrieving product detail"""
        url = reverse("product-detail", kwargs={"slug": self.product.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], self.product.name)
        self.assertEqual(response.data["price"], "49.99")  # Note the string conversion

    def test_create_product(self):
        """Test creating a new product (admin only)"""
        self.authenticate_admin()

        url = reverse("product-list")
        response = self.client.post(url, self.product_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2)
        self.assertAlmostEqual(
            float(Product.objects.get(name="Test Product").price), 99.99, places=2
        )

        # Test that regular users cannot create products
        self.client.credentials()  # Clear credentials
        self.authenticate_user()

        response = self.client.post(url, self.product_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_product(self):
        """Test updating a product (admin only)"""
        self.authenticate_admin()

        url = reverse("product-detail", kwargs={"slug": self.product.slug})
        data = {"price": 59.99, "stock": 15}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["price"], "59.99")  # Note the string conversion
        self.assertEqual(response.data["stock"], 15)

        # Verify in database
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, 59.99)
        self.assertEqual(self.product.stock, 15)

    def test_delete_product(self):
        """Test deleting a product (admin only)"""
        self.authenticate_admin()

        url = reverse("product-detail", kwargs={"slug": self.product.slug})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Product.objects.count(), 0)

    def test_create_review(self):
        """Test creating a product review"""
        self.authenticate_user()

        url = reverse("product-review", kwargs={"slug": self.product.slug})
        response = self.client.post(url, self.review_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.first().rating, 4)
        self.assertEqual(Review.objects.first().user, self.user)

    def test_filter_products(self):
        """Test filtering products"""
        # Create additional products for testing filters
        Product.objects.create(
            name="Cheap Product",
            description="Cheap product description",
            category=self.category,
            price=9.99,
            stock=20,
            is_active=True,
        )

        Product.objects.create(
            name="Expensive Product",
            description="Expensive product description",
            category=self.category,
            price=199.99,
            stock=2,
            is_active=True,
        )

        # Test price filter
        url = reverse("product-list") + "?min_price=100"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Expensive Product")

        # Test category filter
        url = reverse("product-list") + f"?category={self.category.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # All products are in the same category

        # Test in_stock filter
        Product.objects.create(
            name="Out of Stock Product",
            description="Out of stock product description",
            category=self.category,
            price=29.99,
            stock=0,
            is_active=True,
        )

        url = reverse("product-list") + "?in_stock=true"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # Only products with stock > 0

    def test_search_products(self):
        """Test searching products"""
        # Create product for search test
        Product.objects.create(
            name="Special Searchable Item",
            description="This is a unique description for searching",
            category=self.category,
            price=39.99,
            stock=7,
            is_active=True,
        )

        # Test search by name
        url = reverse("product-list") + "?search=Special"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Special Searchable Item")

        # Test search by description
        url = reverse("product-list") + "?search=unique"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Special Searchable Item")

    def test_recommended_products(self):
        """Test product recommendations"""
        url = reverse("product-recommended")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
