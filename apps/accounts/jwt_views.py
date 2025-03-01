from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
    TokenVerifySerializer,
)


class DecoratedTokenObtainPairView(TokenObtainPairView):
    @swagger_auto_schema(
        operation_description="Get JWT token pair (access and refresh tokens) by providing email and password",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "password"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Email address"
                ),
                "password": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Password"
                ),
            },
        ),
        responses={
            status.HTTP_200_OK: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "access": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Access token (JWT)"
                    ),
                    "refresh": openapi.Schema(
                        type=openapi.TYPE_STRING, description="Refresh token (JWT)"
                    ),
                },
            ),
            status.HTTP_401_UNAUTHORIZED: "Invalid credentials",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DecoratedTokenRefreshView(TokenRefreshView):
    @swagger_auto_schema(
        operation_description="Get a new access token by providing a valid refresh token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["refresh"],
            properties={
                "refresh": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Refresh token"
                ),
            },
        ),
        responses={
            status.HTTP_200_OK: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "access": openapi.Schema(
                        type=openapi.TYPE_STRING, description="New access token (JWT)"
                    ),
                },
            ),
            status.HTTP_401_UNAUTHORIZED: "Invalid refresh token",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DecoratedTokenVerifyView(TokenVerifyView):
    @swagger_auto_schema(
        operation_description="Verify that a token is valid",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["token"],
            properties={
                "token": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Token to verify (access or refresh)",
                ),
            },
        ),
        responses={
            status.HTTP_200_OK: "{}",
            status.HTTP_401_UNAUTHORIZED: "Invalid token",
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
