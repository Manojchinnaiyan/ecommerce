from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Cart, CartItem
from apps.accounts.models import User, Address
from apps.products.models import Category, Product
import json


class CartAPITestCase(TestCase):
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
        self.product1 = Product.objects.create(
            name="Product 1",
            description="Product 1 description",
            category=self.category,
            price=19.99,
            stock=10,
            is_active=True,
        )

        self.product2 = Product.objects.create(
            name="Product 2",
            description="Product 2 description",
            category=self.category,
            price=29.99,
            stock=5,
            is_active=True,
        )

        self.out_of_stock_product = Product.objects.create(
            name="Out of Stock Product",
            description="Out of stock product description",
            category=self.category,
            price=39.99,
            stock=0,
            is_active=True,
        )

        # Create carts for each user
        Cart.objects.create(user=self.user)
        Cart.objects.create(user=self.another_user)

        # Cart data
        self.cart_item_data = {"product_id": self.product1.id, "quantity": 2}

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

    def test_get_empty_cart(self):
        """Test retrieving an empty cart"""
        self.authenticate_user()

        url = reverse("cart-my-cart")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items"], 0)
        self.assertEqual(len(response.data["items"]), 0)

    def test_add_item_to_cart(self):
        """Test adding an item to the cart"""
        self.authenticate_user()

        url = reverse("cart-add-item")
        response = self.client.post(url, self.cart_item_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items"], 2)  # Quantity of 2
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["product"]["id"], self.product1.id)
        self.assertEqual(response.data["items"][0]["quantity"], 2)

    def test_add_out_of_stock_item(self):
        """Test adding an out of stock item to cart"""
        self.authenticate_user()

        url = reverse("cart-add-item")
        data = {"product_id": self.out_of_stock_product.id, "quantity": 1}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Either top-level detail or nested in product_id
        self.assertTrue("detail" in response.data or "product_id" in response.data)

    def test_add_more_than_available_stock(self):
        """Test adding more items than available in stock"""
        self.authenticate_user()

        url = reverse("cart-add-item")
        data = {"product_id": self.product2.id, "quantity": 10}  # Only 5 in stock

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Either top-level detail or nested in field
        self.assertTrue(
            "detail" in response.data or any("detail" in str(response.data.values()))
        )

    def test_update_cart_item_quantity(self):
        """Test updating the quantity of a cart item"""
        self.authenticate_user()

        # First add an item
        add_response = self.client.post(
            reverse("cart-add-item"), self.cart_item_data, format="json"
        )
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)

        # Get the cart to find the item ID
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertTrue(len(cart_response.data["items"]) > 0)
        item_id = cart_response.data["items"][0]["id"]

        # Update the quantity
        url = reverse("cart-item-update-quantity", args=[item_id])
        response = self.client.patch(url, {"quantity": 3}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["quantity"], 3)

        # Verify in the cart
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(cart_response.data["total_items"], 3)
        self.assertEqual(cart_response.data["items"][0]["quantity"], 3)

    def test_remove_cart_item(self):
        """Test removing an item from the cart"""
        self.authenticate_user()

        # First add an item
        add_response = self.client.post(
            reverse("cart-add-item"), self.cart_item_data, format="json"
        )
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)

        # Get the cart to find the item ID
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertTrue(len(cart_response.data["items"]) > 0)
        item_id = cart_response.data["items"][0]["id"]

        # Remove the item
        url = reverse("cart-item-remove", args=[item_id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify the cart is empty
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(cart_response.data["total_items"], 0)
        self.assertEqual(len(cart_response.data["items"]), 0)

    def test_clear_cart(self):
        """Test clearing the entire cart"""
        self.authenticate_user()

        # Add multiple items
        add_response1 = self.client.post(
            reverse("cart-add-item"), self.cart_item_data, format="json"
        )
        self.assertEqual(add_response1.status_code, status.HTTP_200_OK)

        add_response2 = self.client.post(
            reverse("cart-add-item"),
            {"product_id": self.product2.id, "quantity": 1},
            format="json",
        )
        self.assertEqual(add_response2.status_code, status.HTTP_200_OK)

        # Verify items were added
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(len(cart_response.data["items"]), 2)

        # Clear the cart
        url = reverse("cart-clear")
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify the cart is empty
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(cart_response.data["total_items"], 0)
        self.assertEqual(len(cart_response.data["items"]), 0)

    def test_cart_isolation(self):
        """Test that carts are isolated between users"""
        # First user adds items
        self.authenticate_user()
        add_response = self.client.post(
            reverse("cart-add-item"), self.cart_item_data, format="json"
        )
        self.assertEqual(add_response.status_code, status.HTTP_200_OK)

        # Create cart for another user if it doesn't exist
        Cart.objects.get_or_create(user=self.another_user)

        # Switch to second user
        self.authenticate_user("another")

        # Second user's cart should be empty
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(cart_response.data["total_items"], 0)

        # Second user adds different items
        add_response2 = self.client.post(
            reverse("cart-add-item"),
            {"product_id": self.product2.id, "quantity": 3},
            format="json",
        )
        self.assertEqual(add_response2.status_code, status.HTTP_200_OK)

        # Switch back to first user
        self.authenticate_user()

        # First user's cart should still have original items
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(cart_response.data["total_items"], 2)
        self.assertEqual(
            cart_response.data["items"][0]["product"]["id"], self.product1.id
        )

    def test_cart_subtotal_calculation(self):
        """Test cart subtotal calculation"""
        self.authenticate_user()

        # Add multiple items
        add_response1 = self.client.post(
            reverse("cart-add-item"), self.cart_item_data, format="json"
        )  # 2 x $19.99
        self.assertEqual(add_response1.status_code, status.HTTP_200_OK)

        add_response2 = self.client.post(
            reverse("cart-add-item"),
            {"product_id": self.product2.id, "quantity": 1},
            format="json",
        )  # 1 x $29.99
        self.assertEqual(add_response2.status_code, status.HTTP_200_OK)

        # Expected subtotal: (2 * 19.99) + (1 * 29.99) = 69.97
        cart_response = self.client.get(reverse("cart-my-cart"))
        expected_subtotal = (2 * 19.99) + (1 * 29.99)

        # Use assertAlmostEqual for floating point comparison
        self.assertAlmostEqual(
            float(cart_response.data["subtotal"]), expected_subtotal, places=2
        )
