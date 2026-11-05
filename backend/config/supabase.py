"""Read-only connectivity check; application data stays behind Django's API."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.core.exceptions import ImproperlyConfigured


def check_project_api(url, publishable_key, opener=urlopen):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".supabase.co")
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise ImproperlyConfigured("SUPABASE_URL must be the clean HTTPS project URL ending in .supabase.co.")
    if not publishable_key or not publishable_key.startswith("sb_publishable_"):
        raise ImproperlyConfigured("Set SUPABASE_PUBLISHABLE_KEY to the project's publishable key. A secret key is not needed for this check.")
    request = Request(url.rstrip("/") + "/auth/v1/settings", headers={
        "apikey": publishable_key,
        "Accept": "application/json",
        "User-Agent": "Queueflow-Django-Connectivity-Check/1.0",
    })
    try:
        with opener(request, timeout=10) as response:
            # Parse a bounded response to verify this is the Auth settings API.
            payload = json.loads(response.read(65_536))
            if not isinstance(payload, dict):
                raise ValueError
    except HTTPError as error:
        raise ImproperlyConfigured(f"Supabase API returned HTTP {error.code}. Check the project URL and publishable key.") from None
    except (URLError, TimeoutError, ValueError):
        raise ImproperlyConfigured("Could not verify the Supabase API. Check network access and project status.") from None
    return parsed.hostname
