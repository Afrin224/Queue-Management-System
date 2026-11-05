"""Prevent direct Data API access to Django-owned records on PostgreSQL."""
from django.db import migrations


def protect_django_tables(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    # Include implicit many-to-many tables and Django's migration ledger.
    # Never alter unrelated Supabase tables, roles, or schema-wide defaults.
    tables = {model._meta.db_table for model in apps.get_models(include_auto_created=True) if model._meta.managed}
    tables.add("django_migrations")
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        roles = [row[0] for row in cursor.fetchall()]
        for table in sorted(tables & existing):
            quoted = connection.ops.quote_name(table)
            cursor.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
            cursor.execute(f"REVOKE ALL ON TABLE {quoted} FROM PUBLIC")
            for role in roles:
                cursor.execute(f"REVOKE ALL ON TABLE {quoted} FROM {connection.ops.quote_name(role)}")
    # No permissive policies: Django uses its trusted database-owner connection
    # and enforces manager ownership. Supabase Auth JWTs are not Django sessions.


class Migration(migrations.Migration):
    dependencies = [
        ("queues", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("sessions", "0001_initial"),
    ]
    # Rolling back queue features must not silently remove database protection.
    operations = [migrations.RunPython(protect_django_tables, migrations.RunPython.noop)]
