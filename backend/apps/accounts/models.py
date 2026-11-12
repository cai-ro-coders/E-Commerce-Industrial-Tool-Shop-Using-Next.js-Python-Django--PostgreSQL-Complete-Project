import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.core.validators import validate_image_upload


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("role", "customer")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("status", "active")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"
        CUSTOMER = "customer", "Customer"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"

    username = None
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=40, blank=True)
    avatar = models.ImageField(
        upload_to="avatars/", null=True, blank=True, validators=[validate_image_upload]
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return self.get_full_name() or self.email.split("@")[0]

    @property
    def is_active_account(self):
        return self.status == "active"

    @property
    def total_spent(self):
        try:
            return self._total_spent
        except AttributeError:
            from django.db.models import Sum

            return (
                self.orders.filter(payment_status="paid").aggregate(total=Sum("grand_total"))[
                    "total"
                ]
                or 0
            )

    @total_spent.setter
    def total_spent(self, value):
        self._total_spent = value

    @property
    def orders_count(self):
        try:
            return self._orders_count
        except AttributeError:
            return self.orders.count()

    @orders_count.setter
    def orders_count(self, value):
        self._orders_count = value


class Address(models.Model):
    user = models.ForeignKey(User, related_name="addresses", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    province = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=30)
    country = models.CharField(max_length=120, default="Philippines")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.full_name} - {self.city}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)

    @property
    def formatted(self):
        parts = [
            self.address_line_1,
            self.address_line_2,
            f"{self.city}, {self.province} {self.postal_code}",
            self.country,
        ]
        return ", ".join(p for p in parts if p)


class LoginHistory(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, related_name="login_history", on_delete=models.SET_NULL
    )
    email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    success = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "login history"

    def __str__(self):
        return f"{self.email} - {'success' if self.success else 'failed'}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, related_name="reset_tokens", on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()


class ActivityLog(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, related_name="activity_logs", on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} by {self.user or 'system'}"
