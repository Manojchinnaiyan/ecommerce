from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import SearchQuery, ProductView, RecommendationEvent
from apps.accounts.models import User
from apps.products.models import Category, Product
import json


class SearchAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="user12345",
            first_name="Test",
            last_name="User",
        )

        # Create category
        self.category = Category.objects.create(
            name="Test Category", description="Test category description"
        )

        # Create products
        self.product1 = Product.objects.create(
            name="Premium Headphones",
            description="Noise cancelling premium headphones",
            category=self.category,
            price=199.99,
            stock=10,
            is_active=True,
        )

        self.product2 = Product.objects.create(
            name="Bluetooth Speaker",
            description="Portable bluetooth speaker with deep bass",
            category=self.category,
            price=99.99,
            stock=15,
            is_active=True,
        )

        self.product3 = Product.objects.create(
            name="Wireless Earbuds",
            description="True wireless earbuds with premium sound",
            category=self.category,
            price=149.99,
            stock=5,
            is_active=True,
        )

        # Search data
        self.search_data = {
            "query": "premium",
            "category_id": None,
            "min_price": None,
            "max_price": None,
            "in_stock": True,
            "rating": None,
            "sort_by": "relevance",
            "page": 1,
            "limit": 10,
        }

        # Recommendation data
        self.recommendation_data = {"product_id": self.product1.id, "limit": 5}

        # Recommendation event data
        self.event_data = {
            "product": self.product1.id,
            "event_type": "click",
            "source": "similar_products",
            "position": 0,
        }

    def authenticate_user(self):
        """Helper method to authenticate user"""
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "user@example.com", "password": "user12345"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_search_products(self):
        """Test searching for products"""
        url = reverse("advanced-search")
        response = self.client.post(url, self.search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 2)  # Should find product1 and product3
        self.assertEqual(len(response.data["results"]), 2)

        # Results should contain products with 'premium' in name or description
        product_names = [p["name"] for p in response.data["results"]]
        self.assertIn("Premium Headphones", product_names)
        self.assertIn("Wireless Earbuds", product_names)
        self.assertNotIn("Bluetooth Speaker", product_names)

    def test_search_with_price_filter(self):
        """Test search with price filter"""
        search_data = dict(self.search_data)
        search_data["min_price"] = 150.00

        url = reverse("advanced-search")
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)  # Should only find product1
        self.assertEqual(response.data["results"][0]["name"], "Premium Headphones")

    def test_search_with_authentication(self):
        """Test search with authenticated user (should record search query)"""
        self.authenticate_user()

        url = reverse("advanced-search")
        response = self.client.post(url, self.search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify search query was recorded
        self.assertEqual(SearchQuery.objects.count(), 1)
        query = SearchQuery.objects.first()
        self.assertEqual(query.user, self.user)
        self.assertEqual(query.query_text, "premium")
        self.assertEqual(query.results_count, 2)

    def test_get_product_recommendations(self):
        """Test getting product recommendations"""
        url = reverse("recommendations")
        response = self.client.post(url, self.recommendation_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        # Should not include the requested product
        product_ids = [p["id"] for p in response.data]
        self.assertNotIn(self.product1.id, product_ids)

    def test_record_recommendation_event(self):
        """Test recording a recommendation event (click)"""
        self.authenticate_user()

        url = reverse("recommendation-event")
        response = self.client.post(url, self.event_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify event was recorded
        self.assertEqual(RecommendationEvent.objects.count(), 1)
        event = RecommendationEvent.objects.first()
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.product, self.product1)
        self.assertEqual(event.event_type, "click")
        self.assertEqual(event.source, "similar_products")

    def test_search_pagination(self):
        """Test search pagination"""
        # Create more products for pagination testing
        for i in range(10):
            Product.objects.create(
                name=f"Premium Product {i}",
                description=f"Premium test product {i}",
                category=self.category,
                price=50.00 + i * 10,
                stock=5,
                is_active=True,
            )

        # Search with pagination (page 1, limit 5)
        search_data = dict(self.search_data)
        search_data["page"] = 1
        search_data["limit"] = 5

        url = reverse("advanced-search")
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)  # Should return 5 products
        self.assertEqual(
            response.data["total"], 12
        )  # Total 12 products with 'premium' in them
        self.assertEqual(response.data["pages"], 3)  # Total 3 pages (12/5 rounded up)

        # Check second page
        search_data["page"] = 2
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)

        # Check third page (should have only 2 products)
        search_data["page"] = 3
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_search_sorting(self):
        """Test search result sorting"""
        # Test price ascending sorting
        search_data = dict(self.search_data)
        search_data["sort_by"] = "price_asc"

        url = reverse("advanced-search")
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Products should be sorted by price (low to high)
        prices = [float(p["price"]) for p in response.data["results"]]
        self.assertEqual(prices, sorted(prices))

        # Test price descending sorting
        search_data["sort_by"] = "price_desc"
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Products should be sorted by price (high to low)
        prices = [float(p["price"]) for p in response.data["results"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

        # Test name sorting
        search_data["sort_by"] = "name_asc"
        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Products should be sorted by name (A to Z)
        names = [p["name"] for p in response.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_category_recommendations(self):
        """Test category-based recommendations"""
        recommendation_data = {"category_id": self.category.id, "limit": 5}

        url = reverse("recommendations")
        response = self.client.post(url, recommendation_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        # Should return products from the category
        self.assertLessEqual(len(response.data), 5)

        # Create a product with high ratings to test sorting
        new_product = Product.objects.create(
            name="Top Rated Product",
            description="Product with high ratings",
            category=self.category,
            price=149.99,
            stock=10,
            is_active=True,
        )

        # Add reviews to simulate high rating
        from apps.products.models import Review

        Review.objects.create(
            product=new_product, user=self.user, rating=5, comment="Excellent product"
        )

        # Get recommendations again
        response = self.client.post(url, recommendation_data, format="json")

        # The top-rated product should appear in results
        product_ids = [p["id"] for p in response.data]
        self.assertIn(new_product.id, product_ids)

    def test_product_view_tracking(self):
        """Test product view tracking for recently viewed products"""
        self.authenticate_user()

        # Access product detail (this should record a view)
        url = reverse("product-detail", kwargs={"slug": self.product1.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify view was recorded
        self.assertEqual(ProductView.objects.count(), 1)
        view = ProductView.objects.first()
        self.assertEqual(view.user, self.user)
        self.assertEqual(view.product, self.product1)

        # Access another product
        url = reverse("product-detail", kwargs={"slug": self.product2.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ProductView.objects.count(), 2)

        # Check recently viewed products
        from apps.products.models import RecentlyViewed

        recently_viewed = RecentlyViewed.objects.filter(user=self.user).order_by(
            "-viewed_at"
        )
        self.assertEqual(recently_viewed.count(), 2)
        self.assertEqual(recently_viewed[0].product, self.product2)  # Most recent
        self.assertEqual(
            recently_viewed[1].product, self.product1
        )  # Second most recent
