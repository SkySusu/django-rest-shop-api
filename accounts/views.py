from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User
from .serializers import BalanceTopUpSerializer, ProfileSerializer, RegistrationSerializer


class RegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveAPIView):
    serializer_class = ProfileSerializer

    def get_object(self):
        return self.request.user


class BalanceTopUpView(APIView):
    """Simulate a user initiated top-up. This endpoint does not process real payments."""

    def post(self, request):
        serializer = BalanceTopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            user.balance += serializer.validated_data["amount"]
            user.save(update_fields=["balance"])
        return Response(ProfileSerializer(user).data, status=status.HTTP_200_OK)
