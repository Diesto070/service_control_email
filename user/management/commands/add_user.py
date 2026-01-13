import os

from django.contrib.auth.models import Group
from django.core.management import BaseCommand, call_command

from config import settings


class Command(BaseCommand):
    help = "Add managers"

    def handle(self, *args, **options):
        managers_group, created = Group.objects.get_or_create(name="Менеджеры")
        if created:
            self.stdout.write(self.style.SUCCESS('Created "Менеджеры" group'))

        fixture_path = os.path.join(settings.BASE_DIR, "users_fixture.json")

        if os.path.exists(fixture_path):
            call_command("loaddata", fixture_path)
            self.stdout.write(self.style.SUCCESS("Successfully loaded fixture data"))
        else:
            self.stdout.write(self.style.ERROR(f"Fixture file not found: {fixture_path}"))
