from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from .models import Payment, Refund
from apps.accounts.models import User, Address
from apps.products.models import Category, Product
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
import json


class PaymentsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="user12345",
            first_name="Test",
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
        self.product = Product.objects.create(
            name="Test Product",
            description="Test product description",
            category=self.category,
            price=99.99,
            stock=10,
            is_active=True,
        )

        # Create an order
        self.order = Order.objects.create(
            user=self.user,
            shipping_address=self.shipping_address,
            billing_address=self.billing_address,
            shipping_name=f"{self.user.first_name} {self.user.last_name}",
            shipping_address_line=self.shipping_address.street_address,
            shipping_city=self.shipping_address.city,
            shipping_state=self.shipping_address.state,
            shipping_postal_code=self.shipping_address.postal_code,
            shipping_country=self.shipping_address.country,
            billing_name=f"{self.user.first_name} {self.user.last_name}",
            billing_address_line=self.billing_address.street_address,
            billing_city=self.billing_address.city,
            billing_state=self.billing_address.state,
            billing_postal_code=self.billing_address.postal_code,
            billing_country=self.billing_address.country,
            subtotal=99.99,
            shipping_cost=10.00,
            tax=10.00,
            total=119.99,
        )

        # Test payment data
        self.payment_data = {"order_id": self.order.id}

        # Mock Razorpay order response
        self.mock_razorpay_order = {
            "id": "order_test123",
            "amount": 11999,  # in paise (119.99 * 100)
            "currency": "INR",
        }

        # Mock Razorpay payment response
        self.mock_razorpay_payment = {
            "id": "pay_test123",
            "order_id": "order_test123",
            "amount": 11999,
            "currency": "INR",
            "status": "captured",
        }

        # Mock verification data
        self.verification_data = {
            "razorpay_payment_id": "pay_test123",
            "razorpay_order_id": "order_test123",
            "razorpay_signature": "test_signature",
        }

    def authenticate_user(self):
        """Helper method to authenticate user"""
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "user@example.com", "password": "user12345"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    @patch("razorpay.Client")
    def test_create_razorpay_order(self, mock_razorpay):
        """Test creating a Razorpay order"""
        self.authenticate_user()

        # Mock Razorpay client
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.order.create.return_value = self.mock_razorpay_order

        url = reverse("payment-create-razorpay-order")
        response = self.client.post(url, {"order_id": self.order.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["razorpay_order_id"], "order_test123")
        self.assertEqual(response.data["amount"], 11999)
        self.assertEqual(response.data["currency"], "INR")

        # Verify Razorpay client was called correctly
        mock_client.order.create.assert_called_once()
        call_args = mock_client.order.create.call_args[0][0]
        self.assertEqual(call_args["amount"], 11999)
        self.assertEqual(call_args["currency"], "INR")
        self.assertEqual(call_args["receipt"], self.order.order_number)

    @patch("razorpay.Client")
    def test_verify_payment(self, mock_razorpay):
        """Test verifying a Razorpay payment"""
        self.authenticate_user()

        # Mock Razorpay client
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.utility.verify_payment_signature.return_value = None  # No error
        mock_client.order.fetch.return_value = {
            "id": "order_test123",
            "notes": {"order_id": str(self.order.id)},
        }
        mock_client.payment.fetch.return_value = self.mock_razorpay_payment

        url = reverse("payment-verify-payment")
        response = self.client.post(url, self.verification_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify payment was created in database
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.payment_id, "pay_test123")
        self.assertEqual(payment.status, "completed")

        # Verify order was updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "paid")
        self.assertEqual(self.order.payment_id, "pay_test123")
        self.assertEqual(self.order.status, "processing")

    @patch("razorpay.Client")
    def test_invalid_payment_verification(self, mock_razorpay):
        """Test invalid payment verification"""
        self.authenticate_user()

        # Mock Razorpay client to raise an exception on verification
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.utility.verify_payment_signature.side_effect = Exception(
            "Invalid signature"
        )

        url = reverse("payment-verify-payment")
        response = self.client.post(url, self.verification_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

        # Verify no payment was created
        self.assertEqual(Payment.objects.count(), 0)

    @patch("razorpay.Client")
    def test_refund_payment(self, mock_razorpay):
        """Test refunding a payment"""
        self.authenticate_user()

        # Create a payment first
        payment = Payment.objects.create(
            order=self.order,
            payment_id="pay_test123",
            amount=119.99,
            currency="INR",
            status="completed",
            razorpay_order_id="order_test123",
            razorpay_signature="test_signature",
        )

        # Update order status
        self.order.payment_status = "paid"
        self.order.payment_id = "pay_test123"
        self.order.status = "processing"
        self.order.save()

        # Mock Razorpay client for refund
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.payment.refund.return_value = {
            "id": "rfnd_test123",
            "payment_id": "pay_test123",
            "amount": 11999,
            "status": "processed",
        }

        url = reverse("refund-request-refund")
        refund_data = {
            "payment_id": "pay_test123",
            "amount": 119.99,
            "reason": "Customer request",
        }

        response = self.client.post(url, refund_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify refund was created in database
        self.assertEqual(Refund.objects.count(), 1)
        refund = Refund.objects.first()
        self.assertEqual(refund.payment, payment)
        self.assertEqual(refund.refund_id, "rfnd_test123")
        self.assertEqual(float(refund.amount), 119.99)
        self.assertEqual(refund.status, "processed")

        # Verify payment was updated
        payment.refresh_from_db()
        self.assertEqual(payment.status, "refunded")

        # Verify order was updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")

    @patch("razorpay.Client")
    def test_partial_refund(self, mock_razorpay):
        """Test partial refund of a payment"""
        self.authenticate_user()

        # Create a payment first
        payment = Payment.objects.create(
            order=self.order,
            payment_id="pay_test123",
            amount=119.99,
            currency="INR",
            status="completed",
            razorpay_order_id="order_test123",
            razorpay_signature="test_signature",
        )

        # Update order status
        self.order.payment_status = "paid"
        self.order.payment_id = "pay_test123"
        self.order.status = "processing"
        self.order.save()

        # Mock Razorpay client for refund
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.payment.refund.return_value = {
            "id": "rfnd_test123",
            "payment_id": "pay_test123",
            "amount": 5000,  # 50.00 in paise
            "status": "processed",
        }

        url = reverse("refund-request-refund")
        refund_data = {
            "payment_id": "pay_test123",
            "amount": 50.00,  # Partial refund
            "reason": "Partial refund for damaged item",
        }

        response = self.client.post(url, refund_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify refund was created
        self.assertEqual(Refund.objects.count(), 1)
        refund = Refund.objects.first()
        self.assertEqual(float(refund.amount), 50.00)

        # For partial refunds, payment status stays completed
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")

        # Order status should not change for partial refunds
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "processing")

    def test_list_user_payments(self):
        """Test retrieving a user's payments"""
        self.authenticate_user()
        url = reverse("payment-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is paginated
        if isinstance(response.data, dict) and "results" in response.data:
            self.assertIsInstance(response.data["results"], list)
        else:
            self.assertIsInstance(response.data, list)

    def test_payment_detail(self):
        """Test retrieving payment details"""
        self.authenticate_user()

        # Create a payment
        payment = Payment.objects.create(
            order=self.order,
            payment_id="pay_test123",
            amount=119.99,
            currency="INR",
            status="completed",
            razorpay_order_id="order_test123",
            razorpay_signature="test_signature",
        )

        url = reverse("payment-detail", args=[payment.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_id"], "pay_test123")
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(float(response.data["amount"]), 119.99)
