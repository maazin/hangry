"""Session slugs and participant tokens."""

import secrets

# Crockford-ish base32 minus vowels and look-alikes: no I/L/O/U, so slugs
# can't spell anything unfortunate and can be read aloud without confusion.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"

SLUG_LENGTH = 6


def new_slug() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(SLUG_LENGTH))


def new_token() -> str:
    """Opaque participant token, stored client-side in localStorage."""
    return secrets.token_urlsafe(24)
