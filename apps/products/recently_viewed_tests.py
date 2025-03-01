from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Category, Product
from .recently_viewed_models import RecentlyViewed
from apps.accounts.models import User
import json


class RecentlyViewedAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="user12345",
            first_name="Test",
            last_name="User",
        )

        # Create another test user for isolation testing
        self.another_user = User.objects.create_user(
            email="another@example.com",
            password="another12345",
            first_name="Another",
            last_name="User",
        )

        # Create category
        self.category = Category.objects.create(
            name="Test Category", description="Test category description"
        )

        # Create products
        self.products = []
        for i in range(1, 6):
            product = Product.objects.create(
                name=f"Product {i}",
                description=f"Description for product {i}",
                category=self.category,
                price=10.00 * i,
                stock=5,
                is_active=True,
            )
            self.products.append(product)

    def authenticate_user(self, user="default"):
        """Helper method to authenticate users"""
        if user == "another":
            credentials = {"email": "another@example.com", "password": "another12345"}
        else:
            credentials = {"email": "user@example.com", "password": "user12345"}

        response = self.client.post(
            reverse("token_obtain_pair"), credentials, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_recently_viewed_tracking(self):
        """Test that viewing products adds them to recently viewed"""
        self.authenticate_user()

        # View multiple products
        for product in self.products[:3]:
            url = reverse("product-detail", kwargs={"slug": product.slug})
            self.client.get(url)

        # Check that recently viewed products were recorded
        recently_viewed = RecentlyViewed.objects.filter(user=self.user).order_by(
            "-viewed_at"
        )
        self.assertEqual(recently_viewed.count(), 3)

        # Products should be in reverse order of viewing (most recent first)
        self.assertEqual(recently_viewed[0].product, self.products[2])
        self.assertEqual(recently_viewed[1].product, self.products[1])
        self.assertEqual(recently_viewed[2].product, self.products[0])

    def test_recently_viewed_list(self):
        """Test retrieving recently viewed products list"""
        self.authenticate_user()

        # First view some products
        for product in self.products:
            url = reverse("product-detail", kwargs={"slug": product.slug})
            self.client.get(url)

        # Get recently viewed products
        url = reverse("recently-viewed-list-products")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

        # Check order (most recent first)
        self.assertEqual(response.data[0]["product"]["id"], self.products[4].id)
        self.assertEqual(response.data[1]["product"]["id"], self.products[3].id)

    def test_recently_viewed_limit(self):
        """Test that recently viewed has a maximum limit"""
        self.authenticate_user()

        # Create more products than the limit
        max_limit = 10  # Default limit
        extra_products = []
        for i in range(6, max_limit + 3):  # Create more than max_limit
            product = Product.objects.create(
                name=f"Product {i}",
                description=f"Description for product {i}",
                category=self.category,
                price=10.00 * i,
                stock=5,
                is_active=True,
            )
            extra_products.append(product)

        # View all products (original + extra)
        all_products = self.products + extra_products
        for product in all_products:
            url = reverse("product-detail", kwargs={"slug": product.slug})
            self.client.get(url)

        # Only max_limit products should be in recently viewed
        recently_viewed = RecentlyViewed.objects.filter(user=self.user)
        self.assertEqual(recently_viewed.count(), max_limit)

        # Get recently viewed products
        url = reverse("recently-viewed-list-products")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), max_limit)

    def test_clear_recently_viewed(self):
        """Test clearing recently viewed products"""
        self.authenticate_user()

        # First view some products
        for product in self.products[:3]:
            url = reverse("product-detail", kwargs={"slug": product.slug})
            self.client.get(url)

        # Verify products were added to recently viewed
        self.assertEqual(RecentlyViewed.objects.filter(user=self.user).count(), 3)

        # Clear recently viewed
        url = reverse("recently-viewed-clear")
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify recently viewed is now empty
        self.assertEqual(RecentlyViewed.objects.filter(user=self.user).count(), 0)

    def test_recently_viewed_isolation(self):
        """Test that recently viewed lists are isolated between users"""
        # First user views some products
        self.authenticate_user()
        for product in self.products[:2]:
            url = reverse("product-detail", kwargs={"slug": product.slug})
            self.client.get(url)

        # Second user views different products
        self.authenticate_user("another")
        for product in self.products[2:4]:
            url = reverse("product-detail", kwargs={"slug": product.slug})
            self.client.get(url)

        # Check first user's recently viewed
        self.authenticate_user()
        url = reverse("recently-viewed-list-products")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        product_ids = [item["product"]["id"] for item in response.data]
        self.assertIn(self.products[0].id, product_ids)
        self.assertIn(self.products[1].id, product_ids)

        # Check second user's recently viewed
        self.authenticate_user("another")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        product_ids = [item["product"]["id"] for item in response.data]
        self.assertIn(self.products[2].id, product_ids)
        self.assertIn(self.products[3].id, product_ids)

    def test_authentication_required(self):
        """Test that authentication is required for recently viewed endpoints"""
        # Attempt to access recently viewed without authentication
        url = reverse("recently-viewed-list-products")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Attempt to clear recently viewed without authentication
        url = reverse("recently-viewed-clear")
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
