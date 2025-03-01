from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Wishlist, WishlistItem
from apps.accounts.models import User
from apps.products.models import Category, Product
from apps.cart.models import Cart, CartItem
import json


class WishlistAPITestCase(TestCase):
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

        # Wishlist data
        self.wishlist_item_data = {"product_id": self.product1.id}

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

    def test_get_empty_wishlist(self):
        """Test retrieving an empty wishlist"""
        self.authenticate_user()

        url = reverse("wishlist-my-wishlist")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items"], 0)
        self.assertEqual(len(response.data["items"]), 0)

    def test_add_item_to_wishlist(self):
        """Test adding an item to the wishlist"""
        self.authenticate_user()

        url = reverse("wishlist-add-item")
        response = self.client.post(url, self.wishlist_item_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_items"], 1)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["product"]["id"], self.product1.id)

    def test_add_duplicate_to_wishlist(self):
        """Test adding the same item twice to wishlist (should fail)"""
        self.authenticate_user()

        url = reverse("wishlist-add-item")
        # Add first time
        self.client.post(url, self.wishlist_item_data, format="json")

        # Try to add again
        response = self.client.post(url, self.wishlist_item_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_remove_wishlist_item(self):
        """Test removing an item from the wishlist"""
        self.authenticate_user()

        # First add an item
        self.client.post(
            reverse("wishlist-add-item"), self.wishlist_item_data, format="json"
        )

        # Get the wishlist to find the item ID
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        item_id = wishlist_response.data["items"][0]["id"]

        # Remove the item
        url = reverse("wishlist-item-remove", args=[item_id])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify the wishlist is empty
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        self.assertEqual(wishlist_response.data["total_items"], 0)
        self.assertEqual(len(wishlist_response.data["items"]), 0)

    def test_clear_wishlist(self):
        """Test clearing the entire wishlist"""
        self.authenticate_user()

        # Add multiple items
        self.client.post(
            reverse("wishlist-add-item"), self.wishlist_item_data, format="json"
        )
        self.client.post(
            reverse("wishlist-add-item"),
            {"product_id": self.product2.id},
            format="json",
        )

        # Verify items were added
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        self.assertEqual(len(wishlist_response.data["items"]), 2)

        # Clear the wishlist
        url = reverse("wishlist-clear")
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify the wishlist is empty
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        self.assertEqual(wishlist_response.data["total_items"], 0)
        self.assertEqual(len(wishlist_response.data["items"]), 0)

    def test_wishlist_isolation(self):
        """Test that wishlists are isolated between users"""
        # First user adds items
        self.authenticate_user()
        self.client.post(
            reverse("wishlist-add-item"), self.wishlist_item_data, format="json"
        )

        # Switch to second user
        self.authenticate_user("another")

        # Second user's wishlist should be empty
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        self.assertEqual(wishlist_response.data["total_items"], 0)

        # Second user adds different items
        self.client.post(
            reverse("wishlist-add-item"),
            {"product_id": self.product2.id},
            format="json",
        )

        # Switch back to first user
        self.authenticate_user()

        # First user's wishlist should still have original items
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        self.assertEqual(wishlist_response.data["total_items"], 1)
        self.assertEqual(
            wishlist_response.data["items"][0]["product"]["id"], self.product1.id
        )

    def test_move_to_cart(self):
        """Test moving an item from wishlist to cart"""
        self.authenticate_user()

        # Add item to wishlist
        self.client.post(
            reverse("wishlist-add-item"), self.wishlist_item_data, format="json"
        )

        # Move to cart
        url = reverse("wishlist-move-to-cart")
        response = self.client.post(url, self.wishlist_item_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify item is no longer in wishlist
        wishlist_response = self.client.get(reverse("wishlist-my-wishlist"))
        self.assertEqual(wishlist_response.data["total_items"], 0)

        # Verify item is now in cart
        cart_response = self.client.get(reverse("cart-my-cart"))
        self.assertEqual(cart_response.data["total_items"], 1)
        self.assertEqual(
            cart_response.data["items"][0]["product"]["id"], self.product1.id
        )

    def test_move_nonexistent_wishlist_item(self):
        """Test moving an item that is not in the wishlist"""
        self.authenticate_user()

        # Try to move an item that's not in the wishlist
        url = reverse("wishlist-move-to-cart")
        response = self.client.post(url, self.wishlist_item_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)
