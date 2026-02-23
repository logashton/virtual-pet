from rest_framework import serializers

from .models import User, temp_personality


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