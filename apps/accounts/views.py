from rest_framework import viewsets, generics, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .models import Address
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    AddressSerializer,
    ChangePasswordSerializer,
)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], serializer_class=ChangePasswordSerializer)
    def change_password(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not user.check_password(serializer.validated_data["old_password"]):
                return Response(
                    {"old_password": ["Wrong password."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Set new password
            user.set_password(serializer.validated_data["new_password"])
            user.save()
            return Response(
                {"message": "Password updated successfully"}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def shipping(self, request):
        shipping_addresses = self.get_queryset().filter(address_type="shipping")
        serializer = self.get_serializer(shipping_addresses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def billing(self, request):
        billing_addresses = self.get_queryset().filter(address_type="billing")
        serializer = self.get_serializer(billing_addresses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response({"message": f"Address set as default {address.address_type}"})
