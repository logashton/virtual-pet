"""
Load sample data for pets, pet_assets, and pet_stats.

Usage:
  python backend/manage.py load_sample_pets

Creates a sample user (if missing), several pets, pet_stats for each pet,
and pet_assets for some pets. Safe to run multiple times; uses get_or_create
for the sample user and creates new pets/assets each run (no duplicate checks).
"""

from django.core.management.base import BaseCommand

from core.models import Pet, PetAsset, PetStats, User


class Command(BaseCommand):
    help = "Load sample pets, pet_assets, and pet_stats (and a sample user if needed)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=int,
            default=None,
            help="Use existing user ID as owner for all sample pets. If not set, creates/uses sample@example.com.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all pets (and their assets/stats) before creating sample data. Does not delete users.",
        )

    def handle(self, *args, **options):
        use_user_id = options["user"]
        clear_first = options["clear"]

        if clear_first:
            deleted_pets = Pet.objects.count()
            Pet.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted_pets} pet(s) (cascade: assets, stats)."))

        if use_user_id:
            try:
                owner = User.objects.get(pk=use_user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with id={use_user_id} not found."))
                return
        else:
            owner, _ = User.objects.get_or_create(
                email="sample@example.com",
                defaults={
                    "username": "sampleuser",
                    "display_name": "Sample User",
                    "is_active": True,
                },
            )
            if _:
                owner.set_password("samplepass123")
                owner.save()
                self.stdout.write("Created sample user: sample@example.com / samplepass123")

        # Sample pets
        pets_data = [
            {"name": "Rex", "visibility": Pet.Visibility.PUBLIC},
            {"name": "Luna", "visibility": Pet.Visibility.PRIVATE},
            {"name": "Rocko", "visibility": Pet.Visibility.PUBLIC},
            {"name": "Mochi", "visibility": Pet.Visibility.UNLISTED},
        ]

        created_pets = []
        for data in pets_data:
            pet = Pet.objects.create(owner=owner, **data)
            PetStats.objects.create(pet=pet)
            created_pets.append(pet)

        self.stdout.write(self.style.SUCCESS(f"Created {len(created_pets)} pets and pet_stats."))

        # Sample pet_assets (placeholder URLs)
        url = "https://placehold.co/600x400"
        assets_data = [
            {"original_image_url": f"{url}", "status": PetAsset.Status.READY, "asset_type": PetAsset.AssetType.IMAGE},
            {"original_image_url": f"{url}", "cutout_image_url": f"{url}", "status": PetAsset.Status.READY},
            {"original_image_url": f"{url}", "status": PetAsset.Status.PENDING, "generator": "placeholder"},
        ]

        for pet, asset_info in zip(created_pets[:3], assets_data):
            PetAsset.objects.create(pet=pet, **asset_info)

        self.stdout.write(self.style.SUCCESS(f"Created {len(assets_data)} pet_assets."))
        self.stdout.write("Done. Use GET /api/pets/?scope=mine (as sample@example.com) or scope=public to list.")
