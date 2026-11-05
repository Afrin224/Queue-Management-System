"""Database selection without exposing connection strings in error messages."""
import ipaddress
from pathlib import Path
from urllib.parse import unquote, urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def is_loopback(hostname):
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def database_configuration(base_dir, environment):
    database_url = environment.get("DATABASE_URL", "").strip()
    if not database_url:
        filename = Path(environment.get("DJANGO_DATABASE_PATH", str(base_dir / "data/django.sqlite3")))
        if not filename.is_absolute():
            filename = base_dir / filename
        filename.parent.mkdir(parents=True, exist_ok=True)
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": filename,
            "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
            "TEST": {"NAME": base_dir / "data/test_django.sqlite3"},
        }

    try:
        parsed = urlsplit(database_url)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname or not parsed.username or not parsed.path.strip("/"):
            raise ValueError
        # Accessing .port also validates malformed/unescaped connection strings.
        parsed.port
        password = unquote(parsed.password or "")
        if "YOUR-PASSWORD" in database_url or "YOUR_PASSWORD" in database_url:
            raise ValueError
        if not is_loopback(parsed.hostname) and not password:
            raise ValueError
        age = int(environment.get("DJANGO_DB_CONN_MAX_AGE", "60"))
        if not 0 <= age <= 600:
            raise ValueError
        config = dj_database_url.parse(database_url, conn_max_age=age, conn_health_checks=True)
    except (ValueError, TypeError, dj_database_url.UnknownSchemeError):
        raise ImproperlyConfigured(
            "DATABASE_URL must be a complete PostgreSQL connection string with its real database password. "
            "Copy it from Supabase → Connect and percent-encode reserved password characters. "
            "An API key cannot replace the database password."
        ) from None

    options = config.setdefault("OPTIONS", {})
    if not is_loopback(parsed.hostname):
        sslmode = options.setdefault("sslmode", "require")
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ImproperlyConfigured("Remote PostgreSQL connections require TLS; use sslmode=require or stronger.")
    # These settings work with Supavisor transaction pooling as well as direct
    # connections: no cursor or prepared-statement state survives a transaction.
    options["prepare_threshold"] = None
    options.setdefault("connect_timeout", 10)
    config["DISABLE_SERVER_SIDE_CURSORS"] = True
    config["TEST"] = {"NAME": "test_queueflow"}
    return config
