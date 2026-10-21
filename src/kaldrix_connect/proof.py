"""The agent's side of a Kaldrix payment: its own key, and a proof made for exactly one payment.

Built from the published format ("Proof of possession" in docs/api/kaldrix-tokens.md) and nothing else. The private key stays in this
process and on this computer; only the signature goes out.
"""

import hashlib
import os
import struct
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ACTION = "payments.initiate"


def new_seed_hex() -> str:
    return os.urandom(32).hex()


def key_from_seed(seed_hex: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def _bytes(b: bytes) -> bytes:
    return struct.pack(">Q", len(b)) + b


def _string(s: str) -> bytes:
    return _bytes(s.encode("utf-8"))


def _option(s):
    return b"\x00" if s is None else b"\x01" + _string(s)


def leaf_block_id(token: dict) -> str:
    """A block's short name: the first 12 bytes of the SHA-256 of its signature, in hex."""
    sig = bytes.fromhex(token["blocks"][-1]["signature"])
    return hashlib.sha256(sig).digest()[:12].hex()


def proof_message(token: dict, resource: str, purpose, amount_minor: int, currency: str, nonce: bytes, issued_at_ms: int) -> bytes:
    return (
        _string("kaldrix.token.use.v2")
        + _string(token["id"])
        + _string(leaf_block_id(token))
        + _string(ACTION)
        + _string(resource)
        + _option(purpose)
        + b"\x01"
        + _string(currency)
        + struct.pack(">Q", amount_minor)
        + _bytes(nonce)
        + struct.pack(">Q", issued_at_ms)
    )


def sign_proof(key: Ed25519PrivateKey, token: dict, recipient_id: str, purpose, amount_minor: int, currency: str = "USD", now_ms=None) -> dict:
    nonce = os.urandom(16)
    at = int(time.time() * 1000) if now_ms is None else now_ms
    msg = proof_message(token, f"payments:recipient:{recipient_id}", purpose, amount_minor, currency, nonce, at)
    return {"nonce": nonce.hex(), "issued_at_ms": at, "signature": key.sign(msg).hex()}
