from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import RegisterSerializer, UserSerializer, CustomTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Match NestJS response: { id, email, name, role, createdAt }
        # Our UserSerializer returns { id, email, name, role, date_joined }
        # We can map date_joined to createdAt if strictly needed.
        user_data = UserSerializer(user).data
        user_data['createdAt'] = user_data.pop('date_joined')
        
        return Response(user_data, status=status.HTTP_201_CREATED)

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db import IntegrityError
from .models import GuardianInvitation, GuardianProfile, User
from .serializers import GuardianInvitationSerializer

class InviteGuardianView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != User.Role.OWNER:
            return Response({"error": "Only owners can invite guardians"}, status=status.HTTP_403_FORBIDDEN)
            
        email = request.data.get('email')
        phone_number = request.data.get('phone_number')
        
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Prevent inviting if user already exists
        if User.objects.filter(email=email).exists():
            return Response({"error": "User with this email already exists"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            invitation = GuardianInvitation.objects.create(
                owner=request.user,
                email=email,
                phone_number=phone_number
            )
            serializer = GuardianInvitationSerializer(invitation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response({"error": "Failed to create invitation"}, status=status.HTTP_400_BAD_REQUEST)

class ListGuardiansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.OWNER:
            return Response({"error": "Only owners can view their guardians"}, status=status.HTTP_403_FORBIDDEN)
        
        invites = GuardianInvitation.objects.filter(owner=request.user).order_by('-created_at')
        invites_serializer = GuardianInvitationSerializer(invites, many=True)
        
        return Response({
            "active": [],
            "pending": invites_serializer.data
        }, status=status.HTTP_200_OK)


class HealthView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
