from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'name', 'role']

    def create(self, validated_data):
        # We need to ensure username is set. We'll use email as username.
        validated_data['username'] = validated_data['email']
        user = User.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add custom response data matching NestJS
        # NestJS: { accessToken: string, user: UserResponse }
        
        response = {
            'accessToken': data['access'],
            'user': UserSerializer(self.user).data
        }
        # We can also include refresh token if needed, but Flutter app seems to expect accessToken
        # If the app needs refresh token, we should include it. The plan says "accessToken: <jwt>".
        # I'll include 'refreshToken' just in case, but mapped from 'refresh'.
        if 'refresh' in data:
            response['refreshToken'] = data['refresh']
            
        return response

from .models import GuardianInvitation

class GuardianInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardianInvitation
        fields = ['id', 'email', 'phone_number', 'token', 'is_used', 'created_at']
        read_only_fields = ['id', 'token', 'is_used', 'created_at']

