import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from api.config import settings

logger = logging.getLogger(__name__)

TRIAL_DAYS = 7


def _canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _load_private_key() -> rsa.RSAPrivateKey | None:
    pem_b64 = settings.GASIFAC_PRIVATE_KEY
    if not pem_b64:
        logger.warning("GASIFAC_PRIVATE_KEY not set")
        return None
    try:
        pem = base64.b64decode(pem_b64)
        key = serialization.load_pem_private_key(pem, password=None)
        if isinstance(key, rsa.RSAPrivateKey):
            return key
    except Exception as e:
        logger.warning("Could not load private key: %s", e)
    return None


def generate_pro_license(machine_id: str, email: str) -> dict | None:
    key = _load_private_key()
    if key is None:
        logger.error("Cannot generate license: no private key")
        return None

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=31)).isoformat()

    payload = {
        "type": "pro",
        "machine_id": machine_id,
        "email": email,
        "company": "",
        "issued_at": now.isoformat(),
        "expires_at": expires_at,
    }

    canonical = _canonical_json(payload)
    sig = key.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    signature_b64 = base64.b64encode(sig).decode()

    return {
        **payload,
        "signature": signature_b64,
    }
