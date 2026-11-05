from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from config.supabase import check_project_api


class Command(BaseCommand):
    help = "Verify the Supabase API and Django's PostgreSQL connection without displaying credentials."

    def add_arguments(self, parser):
        parser.add_argument("--api-only", action="store_true", help="Check the publishable key without a database password.")

    def handle(self, *args, **options):
        try:
            hostname = check_project_api(settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY)
        except ImproperlyConfigured as error:
            raise CommandError(str(error)) from None
        self.stdout.write(self.style.SUCCESS(f"Supabase API verified: {hostname}. Publishable key accepted."))
        if options["api_only"]:
            return
        if connection.vendor != "postgresql":
            raise CommandError("Django still uses SQLite. Add the completed DATABASE_URL to .env, then run this check again.")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                cursor.fetchone()
        except DatabaseError:
            raise CommandError("PostgreSQL connection failed. Verify DATABASE_URL, the database password, TLS, and the selected direct/pooler endpoint.") from None
        self.stdout.write(self.style.SUCCESS("Django PostgreSQL connection verified."))
