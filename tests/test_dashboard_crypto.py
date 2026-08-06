"""
Unit tests for the dashboard's AES-256-CBC session encryption
(no network / no server start required).
"""
import base64
import os

from dashboard.server import _decrypt_cbc, _derive_key


def _encrypt_cbc(aes_key: bytes, plain: str) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_pad

    iv = os.urandom(16)
    enc = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).encryptor()
    padder = sym_pad.PKCS7(128).padder()
    padded = padder.update(plain.encode("utf-8")) + padder.finalize()
    ct = enc.update(padded) + enc.finalize()
    return base64.b64encode(iv + ct).decode("ascii")


def test_derive_key_is_32_bytes():
    key = _derive_key("ABC123")
    assert len(key) == 32


def test_derive_key_is_deterministic():
    assert _derive_key("ABC123") == _derive_key("ABC123")
    assert _derive_key("ABC123") != _derive_key("XYZ987")


def test_decrypt_roundtrip():
    key = _derive_key("SESSIONKEY")
    payload = "tell ultron to open chrome"
    assert _decrypt_cbc(key, _encrypt_cbc(key, payload)) == payload


def test_wrong_key_fails():
    payload = "secret"
    enc = _encrypt_cbc(_derive_key("RIGHT"), payload)
    assert _decrypt_cbc(_derive_key("WRONG"), enc) is None


def test_tampered_ciphertext_fails():
    key = _derive_key("K")
    enc = _encrypt_cbc(key, "data")
    raw = bytearray(base64.b64decode(enc))
    raw[-1] ^= 0xFF
    assert _decrypt_cbc(key, base64.b64encode(bytes(raw)).decode()) is None
