from decimal import Decimal

from django.contrib.auth import authenticate
from django.db.models import Q, Sum
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import (
    ActivityLog,
    Address,
    LoginHistory,
    User,
)


class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    orders_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "role",
            "phone", "avatar", "status", "is_active", "last_login",
            "date_joined", "orders_count", "total_spent",
        ]


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=False)
    orders_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "role",
            "phone", "avatar", "avatar_url", "status", "is_active", "is_staff",
            "is_superuser", "last_login", "date_joined", "password",
            "confirm_password", "orders_count", "total_spent",
        ]
        read_only_fields = ["id", "last_login", "date_joined", "is_superuser"]
        extra_kwargs = {"is_staff": {"required": False}}

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
        return None

    def validate_email(self, value):
        value = value.lower().strip()
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        confirm = attrs.get("confirm_password")
        if password and confirm is not None and password != confirm:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if not self.instance and not password:
            raise serializers.ValidationError({"password": "Password is required."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "role",
            "phone", "avatar", "avatar_url", "status", "last_login",
            "date_joined", "addresses", "orders_count", "total_spent",
        ]
        read_only_fields = ["id", "email", "role", "status", "last_login", "date_joined"]
        extra_kwargs = {"avatar": {"required": False}}

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
        return None

    def get_addresses(self, obj):
        return AddressSerializer(obj.addresses.all(), many=True).data

    def get_orders_count(self, obj):
        return obj.orders.count()

    def get_total_spent(self, obj):
        total = obj.orders.filter(payment_status="paid").aggregate(total=Sum("grand_total"))[
            "total"
        ]
        return total or Decimal("0.00")


class AddressSerializer(serializers.ModelSerializer):
    formatted = serializers.CharField(read_only=True)

    class Meta:
        model = Address
        fields = [
            "id", "user", "full_name", "phone", "address_line_1",
            "address_line_2", "city", "province", "postal_code", "country",
            "is_default", "formatted", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class LoginHistorySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = LoginHistory
        fields = ["id", "user", "user_name", "email", "ip_address", "user_agent", "success", "created_at"]

    def get_user_name(self, obj):
        return obj.user.full_name if obj.user else obj.email


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ["id", "user", "user_name", "action", "description", "entity_type", "entity_id", "ip_address", "created_at"]

    def get_user_name(self, obj):
        return obj.user.full_name if obj.user else "System"


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)

    def validate(self, attrs):
        email = attrs["email"].lower().strip()
        user = User.objects.filter(Q(email=email)).first()
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if user.status != "active":
            raise serializers.ValidationError("This account is not active. Contact support.")
        authenticated = authenticate(username=user.email, password=attrs["password"])
        if not authenticated:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = authenticated
        return attrs

    @classmethod
    def get_token(cls, user):
        token = TokenObtainPairSerializer.get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.full_name
        token["user_id"] = user.id
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "password", "confirm_password"]

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower().strip()

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        user = User(role="customer", status="active", **validated_data)
        user.set_password(password)
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": "New password must be different."})
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    orders_count = serializers.IntegerField(read_only=True)
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "phone",
            "avatar", "avatar_url", "status", "is_active", "date_joined",
            "last_login", "orders_count", "total_spent", "addresses",
            "password", "confirm_password",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.avatar:
            return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
        return None

    def validate_email(self, value):
        value = value.lower().strip()
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Password is required for a new customer."})
        if attrs.get("password") and attrs.get("confirm_password") is not None:
            if attrs["password"] != attrs["confirm_password"]:
                raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        validated_data.pop("confirm_password", None)
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
