from rest_framework import serializers

from .models import Pet, PetStats, User, temp_personality, PetAsset



class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ("id", "email", "username", "display_name")
        read_only_fields = fields


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
        fields = ('id', 'original_image_url', 'cutout_image_url', 'status', 'asset_type')

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
    