from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        GUARDIAN = 'GUARDIAN', 'Guardian'
        ADMIN = 'ADMIN', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    
    # We use email as the unique identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username'] # username is required by AbstractUser, so we must keep it in required fields or handle it. 
    # Actually if USERNAME_FIELD is email, then email is required. username should be in REQUIRED_FIELDS if we want to prompt for it.
    # But we want to login with email.
    
    def __str__(self):
        return self.email

class OwnerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='owner_profile')
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Owner: {self.user.email}"

class GuardianProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guardian_profile')
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Guardian: {self.user.email} (Approved: {self.approved})"

class GuardianInvitation(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite to {self.email} from {self.owner.email}"

# Signals to auto-create profiles
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == User.Role.OWNER:
            OwnerProfile.objects.create(user=instance)
        elif instance.role == User.Role.GUARDIAN:
            GuardianProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if instance.role == User.Role.OWNER and hasattr(instance, 'owner_profile'):
        instance.owner_profile.save()
    elif instance.role == User.Role.GUARDIAN and hasattr(instance, 'guardian_profile'):
        instance.guardian_profile.save()
