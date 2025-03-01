from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Order, OrderItem
from apps.accounts.models import User, Address
from apps.products.models import Category, Product
from apps.cart.models import Cart, CartItem
import json


class OrdersAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="user12345",
            first_name="Test",
            last_name="User",
        )

        # Create admin user
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="admin12345",
            first_name="Admin",
            last_name="User",
        )

        # Create addresses for the user
        self.shipping_address = Address.objects.create(
            user=self.user,
            address_type="shipping",
            street_address="123 Shipping St",
            city="Shipping City",
            state="Shipping State",
            postal_code="12345",
            country="Shipping Country",
            is_default=True,
        )

        self.billing_address = Address.objects.create(
            user=self.user,
            address_type="billing",
            street_address="456 Billing St",
            city="Billing City",
            state="Billing State",
            postal_code="67890",
            country="Billing Country",
            is_default=True,
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

        # Create cart for user
        Cart.objects.create(user=self.user)

        # Create cart for admin
        Cart.objects.create(user=self.admin)

        # Order creation data
        self.order_data = {
            "shipping_address_id": self.shipping_address.id,
            "billing_address_id": self.billing_address.id,
            "shipping_cost": 5.00,
        }

    def authenticate_user(self, admin=False):
        """Helper method to authenticate user or admin"""
        if admin:
            credentials = {"email": "admin@example.com", "password": "admin12345"}
        else:
            credentials = {"email": "user@example.com", "password": "user12345"}

        response = self.client.post(
            reverse("token_obtain_pair"), credentials, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def setup_cart(self):
        """Helper method to set up a cart with items for the test user"""
        self.authenticate_user()

        # Make sure user has a cart
        try:
            cart = self.user.cart
        except Cart.DoesNotExist:
            cart = Cart.objects.create(user=self.user)

        # Clear any existing items
        cart.items.all().delete()

        # Add new items
        CartItem.objects.create(cart=cart, product=self.product1, quantity=2)
        CartItem.objects.create(cart=cart, product=self.product2, quantity=1)

        # Verify items were added
        self.assertEqual(cart.items.count(), 2)

    def test_create_order_from_cart(self):
        """Test creating an order from items in cart"""
        self.setup_cart()

        url = reverse("order-list")
        response = self.client.post(url, self.order_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("order_number", response.data)

        # Verify order was created in database
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()

        # Check order details
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.shipping_address, self.shipping_address)
        self.assertEqual(order.billing_address, self.billing_address)

        # Check order items
        self.assertEqual(order.items.count(), 2)

        # Check calculated totals
        # Subtotal should be (2 * 19.99) + (1 * 29.99) = 69.97
        expected_subtotal = (2 * 19.99) + (1 * 29.99)
        # Tax should be 10% of subtotal = 6.997
        expected_tax = expected_subtotal * 0.1
        # Total should be subtotal + shipping_cost + tax = 69.97 + 5.00 + 6.997 = 81.967
        expected_total = expected_subtotal + 5.00 + expected_tax

        # Use assertAlmostEqual with places=2 to handle decimal precision issues
        self.assertAlmostEqual(float(order.subtotal), expected_subtotal, places=2)
        self.assertAlmostEqual(float(order.tax), expected_tax, places=2)
        self.assertAlmostEqual(float(order.total), expected_total, places=2)

        # Verify cart is now empty
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)

    def test_create_order_with_empty_cart(self):
        """Test creating an order with an empty cart (should fail)"""
        self.authenticate_user()

        # Make sure the user has a cart
        try:
            cart = self.user.cart
        except Cart.DoesNotExist:
            cart = Cart.objects.create(user=self.user)

        # Ensure the cart is empty
        cart.items.all().delete()

        url = reverse("order-list")
        response = self.client.post(url, self.order_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cart", response.data)  # Should have an error about empty cart

    def test_get_user_orders(self):
        """Test retrieving a user's orders"""
        # Create an order first
        self.setup_cart()
        self.client.post(reverse("order-list"), self.order_data, format="json")

        # Get the orders
        url = reverse("order-my-orders")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)  # Just check there are orders
        # Check the first order has the expected status
        if response.data:
            self.assertEqual(response.data[0]["status"], "pending")

    def test_get_order_detail(self):
        """Test retrieving order details"""
        # Create an order first
        self.setup_cart()
        order_response = self.client.post(
            reverse("order-list"), self.order_data, format="json"
        )
        order_id = order_response.data["id"]

        # Get the order details
        url = reverse("order-detail", args=[order_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], order_id)
        self.assertEqual(len(response.data["items"]), 2)

    def test_cancel_order(self):
        """Test cancelling an order"""
        # Create an order first
        self.setup_cart()
        order_response = self.client.post(
            reverse("order-list"), self.order_data, format="json"
        )
        order_id = order_response.data["id"]

        # Cancel the order
        url = reverse("order-cancel", args=[order_id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelled")

        # Verify in database
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, "cancelled")

    def test_admin_access_all_orders(self):
        """Test that admins can see all orders"""
        # Create an order as regular user
        self.setup_cart()
        self.client.post(reverse("order-list"), self.order_data, format="json")

        # Switch to admin user
        self.authenticate_user(admin=True)

        # Admin should see all orders
        url = reverse("order-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)  # Just check there are orders

    def test_admin_update_order_status(self):
        """Test that admins can update order status"""
        # Create an order as regular user
        self.setup_cart()
        order_response = self.client.post(
            reverse("order-list"), self.order_data, format="json"
        )
        order_id = order_response.data["id"]

        # Switch to admin user
        self.authenticate_user(admin=True)

        # Update order status
        url = reverse("order-detail", args=[order_id])
        response = self.client.patch(url, {"status": "processing"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "processing")

        # Verify in database
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, "processing")

    def test_user_isolation(self):
        """Test that users can only see their own orders"""
        # Create an order as first user
        self.setup_cart()
        self.client.post(reverse("order-list"), self.order_data, format="json")

        # Create another user
        second_user = User.objects.create_user(
            email="second@example.com",
            password="second12345",
            first_name="Second",
            last_name="User",
        )
        # Create cart for second user
        Cart.objects.create(user=second_user)

        # Authenticate as second user
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "second@example.com", "password": "second12345"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

        # Check my-orders endpoint instead of order-list
        url = reverse("order-my-orders")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Second user should see no orders
        self.assertEqual(len(response.data), 0)

    def test_order_item_details(self):
        """Test retrieving order item details"""
        # Create an order first
        self.setup_cart()

        url = reverse("order-list")
        order_response = self.client.post(url, self.order_data, format="json")
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)

        order_id = order_response.data["id"]

        # Get the order items
        url = reverse("order-items-list", kwargs={"order_pk": order_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check we have the expected number of items (2 in setup_cart)
        self.assertEqual(len(response.data), 2)
