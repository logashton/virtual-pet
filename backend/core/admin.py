from django.contrib import admin

from . import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "username", "is_active", "is_staff", "is_superuser", "created_at")
    search_fields = ("email", "username", "display_name")


admin.site.register(models.Role)
admin.site.register(models.UserRole)
admin.site.register(models.Pet)
admin.site.register(models.PetPersonality)
admin.site.register(models.PetAsset)
admin.site.register(models.PetStats)
admin.site.register(models.PetActionLog)
admin.site.register(models.ChatSession)
admin.site.register(models.ChatMessage)
admin.site.register(models.UserPetFollow)
admin.site.register(models.PetLike)
admin.site.register(models.ModerationReport)
admin.site.register(models.ContentScan)
admin.site.register(models.AuthSession)

