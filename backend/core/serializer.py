from rest_framework import serializers

from .models import Pet, PetStats, User, temp_personality, PetAsset, ModerationReport


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ("id", "email", "username", "display_name", "is_staff", "is_superuser")
        read_only_fields = fields


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "display_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class AdminUserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(max_length=50, required=False)
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    is_superuser = serializers.BooleanField(required=False)

    def validate_email(self, value):
        if value and self.instance:
            if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if value and self.instance:
            if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("A user with this username already exists.")
        return value

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    username = serializers.CharField(max_length=50, write_only=True)
    password = serializers.CharField(min_length=8, write_only=True, style={"input_type": "password"})
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        display_name = validated_data.pop("display_name", "") or None
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
            display_name=display_name,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class Temp_PersonalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = temp_personality
        fields = "__all__"


# --- Pets ---


class PetOwnerSerializer(serializers.ModelSerializer):
    # owner info for pet responses

    class Meta:
        model = User
        fields = ("id", "username", "display_name")


class PetSerializer(serializers.ModelSerializer):
    owner = PetOwnerSerializer(read_only=True)

    class Meta:
        model = Pet
        fields = (
            "id",
            "owner",
            "name",
            "visibility",
            "is_archived",
            "created_at",
            "updated_at",
            "last_interaction_at",
        )
        read_only_fields = ("id", "owner", "created_at", "updated_at", "last_interaction_at")


class PetCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    visibility = serializers.ChoiceField(choices=Pet.Visibility.choices, default=Pet.Visibility.PRIVATE, required=False)
    is_archived = serializers.BooleanField(default=False, required=False)

    def create(self, validated_data):
        owner = self.context["request"].user
        pet = Pet.objects.create(owner=owner, **validated_data)
        PetStats.objects.create(pet=pet)
        return pet


class PetUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, required=False)
    visibility = serializers.ChoiceField(choices=Pet.Visibility.choices, required=False)
    is_archived = serializers.BooleanField(required=False)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
   
   
class PetAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PetAsset
        fields = ('id', 'original_image_url', 'cutout_image_url', 'model_3d_url', 'status', 'asset_type')

class PetSerializer(serializers.ModelSerializer):
    owner = PetOwnerSerializer(read_only=True)
    assets = PetAssetSerializer(many=True, read_only=True)  

    class Meta:
        model = Pet
        fields = (
            "id", "owner", "name", "visibility", "is_archived",
            "created_at", "updated_at", "last_interaction_at",
            "assets",  
        )
        read_only_fields = ("id", "owner", "created_at", "updated_at", "last_interaction_at", "assets") 
    


# --- Moderation reports ---


class ModerationReportSerializer(serializers.ModelSerializer):
    reporter_user = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    pet = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    asset = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)

    class Meta:
        model = ModerationReport
        fields = (
            "id",
            "reporter_user",
            "pet",
            "asset",
            "reason",
            "details",
            "status",
            "created_at",
            "resolved_at",
        )
        read_only_fields = ("id", "reporter_user", "created_at")


class ModerationReportCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=80)
    details = serializers.CharField(required=False, allow_blank=True, default="")
    pet_id = serializers.IntegerField(required=False, allow_null=True)
    asset_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get("pet_id") and not data.get("asset_id"):
            raise serializers.ValidationError("Provide at least one of pet_id or asset_id.")
        return data

    def create(self, validated_data):
        pet_id = validated_data.get("pet_id")
        asset_id = validated_data.get("asset_id")
        report = ModerationReport.objects.create(
            reporter_user=self.context["request"].user,
            pet_id=pet_id,
            asset_id=asset_id,
            reason=validated_data["reason"],
            details=validated_data.get("details") or None,
        )
        return report


class ModerationReportUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ModerationReport.Status.choices, required=False)
    resolved_at = serializers.DateTimeField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        return instance
