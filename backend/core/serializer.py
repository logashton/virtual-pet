from rest_framework import serializers

from .models import temp_personality


class Temp_PersonalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = temp_personality
        fields = "__all__"