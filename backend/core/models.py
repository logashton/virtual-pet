from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, username: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        if not username:
            raise ValueError("The given username must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        if password is not None:
            user.set_password(password)
        else:
            # Leaves password_hash empt caller can populate manually
            user.password = ""
        user.save(using=self._db)
        return user

    def create_user(self, email: str, username: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email: str, username: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser):
    """
    existing users table

    note map Django's password field onto password_hash (db_column)
    """

    id = models.BigAutoField(primary_key=True)

    email = models.EmailField(max_length=255, unique=True)
    username = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=80, blank=True, null=True)

    # AbstractBaseUser defines password and last_login. 
    # map password to password_hash
    password = models.CharField(max_length=255, db_column="password_hash")
    password_salt = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        if not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username


class Role(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "roles"

    def __str__(self) -> str:
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id", related_name="role_users")

    class Meta:
        db_table = "user_roles"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.role_id}"


class Pet(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "private"
        PUBLIC = "public", "public"
        UNLISTED = "unlisted", "unlisted"

    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, db_column="owner_id", related_name="pets")
    name = models.CharField(max_length=60)
    visibility = models.CharField(max_length=20, default=Visibility.PRIVATE, choices=Visibility.choices)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)
    last_interaction_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "pets"
        indexes = [
            models.Index(fields=["owner"], name="idx_pets_owner_id"),
            models.Index(fields=["visibility"], name="idx_pets_visibility"),
        ]

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        if not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} (#{self.id})"


class PetPersonality(models.Model):
    id = models.BigAutoField(primary_key=True)
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="personality")
    roleplay_prompt = models.TextField()
    traits = models.JSONField(default=dict)
    tone = models.CharField(max_length=40, blank=True, null=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "pet_personalities"

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class PetAsset(models.Model):
    class AssetType(models.TextChoices):
        IMAGE = "image", "image"
        MODEL_3D = "3d", "3d"
        OTHER = "other", "other"

    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        READY = "ready", "ready"
        FAILED = "failed", "failed"

    id = models.BigAutoField(primary_key=True)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="assets")
    original_image_url = models.TextField()
    cutout_image_url = models.TextField(blank=True, null=True)
    model_3d_url = models.TextField(blank=True, null=True)
    asset_type = models.CharField(max_length=20, default=AssetType.IMAGE, choices=AssetType.choices)
    generator = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default=Status.PENDING, choices=Status.choices)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "pet_assets"
        indexes = [
            models.Index(fields=["pet"], name="idx_pet_assets_pet_id"),
        ]


class PetStats(models.Model):
    id = models.BigAutoField(primary_key=True)
    pet = models.OneToOneField(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="stats")
    hunger = models.IntegerField(default=50)
    energy = models.IntegerField(default=50)
    happiness = models.IntegerField(default=50)
    cleanliness = models.IntegerField(default=50)
    health = models.IntegerField(default=100)
    level = models.IntegerField(default=1)
    experience = models.IntegerField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "pet_stats"
        constraints = [
            models.CheckConstraint(condition=Q(hunger__gte=0, hunger__lte=100), name="chk_pet_stats_hunger_0_100"),
            models.CheckConstraint(condition=Q(energy__gte=0, energy__lte=100), name="chk_pet_stats_energy_0_100"),
            models.CheckConstraint(condition=Q(happiness__gte=0, happiness__lte=100), name="chk_pet_stats_happiness_0_100"),
            models.CheckConstraint(condition=Q(cleanliness__gte=0, cleanliness__lte=100), name="chk_pet_stats_cleanliness_0_100"),
            models.CheckConstraint(condition=Q(health__gte=0, health__lte=100), name="chk_pet_stats_health_0_100"),
            models.CheckConstraint(condition=Q(level__gte=1), name="chk_pet_stats_level_gte_1"),
            models.CheckConstraint(condition=Q(experience__gte=0), name="chk_pet_stats_experience_gte_0"),
        ]

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class PetActionLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="action_logs")
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="pet_actions")
    action_type = models.CharField(max_length=30)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "pet_action_log"
        indexes = [
            models.Index(fields=["pet", "created_at"], name="idx_pact_pet_created"),
        ]


class ChatSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="chat_sessions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="chat_sessions")
    model = models.CharField(max_length=80, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    last_message_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "chat_sessions"
        indexes = [
            models.Index(fields=["pet"], name="idx_chat_sessions_pet_id"),
        ]


class ChatMessage(models.Model):
    class Sender(models.TextChoices):
        USER = "user", "user"
        PET = "pet", "pet"
        SYSTEM = "system", "system"

    id = models.BigAutoField(primary_key=True)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, db_column="session_id", related_name="messages")
    sender = models.CharField(max_length=20, choices=Sender.choices)
    content = models.TextField()
    tokens_in = models.IntegerField(blank=True, null=True)
    tokens_out = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "chat_messages"
        indexes = [
            models.Index(fields=["session", "created_at"], name="idx_cmsg_sess_created"),
        ]


class UserPetFollow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="pet_follows")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="followers")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "user_pet_follows"
        constraints = [
            models.UniqueConstraint(fields=["user", "pet"], name="uniq_user_pet_follow"),
        ]


class PetLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="pet_likes")
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, db_column="pet_id", related_name="likes")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "pet_likes"
        constraints = [
            models.UniqueConstraint(fields=["user", "pet"], name="uniq_user_pet_like"),
        ]


class ModerationReport(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "open"
        RESOLVED = "resolved", "resolved"
        REJECTED = "rejected", "rejected"

    id = models.BigAutoField(primary_key=True)
    reporter_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column="reporter_user_id",
        related_name="moderation_reports_filed",
    )
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, blank=True, null=True, db_column="pet_id", related_name="reports")
    asset = models.ForeignKey(
        PetAsset, on_delete=models.CASCADE, blank=True, null=True, db_column="asset_id", related_name="reports"
    )
    reason = models.CharField(max_length=80)
    details = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default=Status.OPEN, choices=Status.choices)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "moderation_reports"
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_mrep_status_created"),
        ]


class ContentScan(models.Model):
    id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(PetAsset, on_delete=models.CASCADE, db_column="asset_id", related_name="content_scans")
    provider = models.CharField(max_length=60)
    verdict = models.CharField(max_length=30)
    score = models.DecimalField(max_digits=6, decimal_places=5, blank=True, null=True)
    raw = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "content_scans"
        indexes = [
            models.Index(fields=["asset", "created_at"], name="idx_cscan_asset_created"),
        ]


class AuthSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", related_name="auth_sessions")
    refresh_token_hash = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "auth_sessions"
        indexes = [
            models.Index(fields=["user", "expires_at"], name="idx_asess_user_expires"),
        ]

