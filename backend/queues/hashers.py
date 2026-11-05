"""Verify imported Node credentials, then upgrade them on successful login."""
import hashlib
import hmac

from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LegacyNodeScryptHasher(BasePasswordHasher):
    algorithm = "node_scrypt"

    def encode(self, password, salt):
        derived = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=64, maxmem=64 * 1024 * 1024)
        return f"{self.algorithm}${salt}${derived.hex()}"

    def verify(self, password, encoded):
        try:
            algorithm, salt, expected = encoded.split("$")
            if algorithm != self.algorithm:
                return False
            return hmac.compare_digest(self.encode(password, salt), encoded)
        except (ValueError, TypeError):
            return False

    def safe_summary(self, encoded):
        algorithm, salt, derived = encoded.split("$")
        return {"algorithm": algorithm, "salt": mask_hash(salt), "hash": mask_hash(derived)}

    def must_update(self, encoded):
        return True
