"""SEU1 ciphertext container engine.

Business/crypto layer for the Secure Encryption Utility.

<!--- CIPHERTEXT FILE FORMAT (SEU1) -------------------------------------------
Byte offset  Length   Field
-----------  -------  -------------------------------------------------------
0            4        Magic bytes: 0x53 0x45 0x55 0x31 ("SEU1")
4            1        Algorithm ID: 0x01=AES-GCM, 0x02=AES-CBC+HMAC,
                      0x03=ChaCha20-Poly1305, 0x04=RSA-OAEP+AES-GCM
5            1        Container version: 0x01
6            2        Reserved: 0x00 0x00
8            16       Salt (PBKDF2 for passphrase mode, zeros for key mode)
24           0 or 512   RSA-OAEP-wrapped data key (algo 0x04 only);
                        512 bytes for a 4096-bit RSA modulus
24/536       16       IV / nonce field (GCM/ChaCha nonce occupies the first
                            12 bytes, CBC uses all 16)
+            4        Original filename length (uint32 little-endian)
+            N        Original filename (UTF-8)
+            16/32    Authentication tag (GCM/Poly1305: 16, CBC HMAC: 32)
+            R        Ciphertext
------------------------------------------------------------------------------->
"""

import base64
import os
import struct

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms as ciph
from cryptography.hazmat.primitives.ciphers import modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"SEU1"
VERSION = 1

ALGO_GCM = 1
ALGO_CBC = 2
ALGO_CHACHA = 3
ALGO_RSA = 4

ALGO_NAMES = {
    1: "AES-256-GCM",
    2: "AES-256-CBC + HMAC",
    3: "ChaCha20-Poly1305",
    4: "RSA-4096 + AES-256",
}

DEFAULT_ALGO = ALGO_GCM
SALT_SIZE = 16
PBKDF2_ITERATIONS = 600000  # OWASP 2023+ recommendation
GCM_NONCE = 12
CHACHA_NONCE = 12
CBC_IV = 16
HMAC_TAG = 32
AEAD_TAG = 16


class SeuError(Exception):
    pass


class SeuFormatError(SeuError):
    pass


def algo_id(name):
    for aid, aname in ALGO_NAMES.items():
        if aname == name:
            return aid
    raise ValueError("unknown algorithm: %s" % name)


def derive_key(password, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _hmac(key, data):
    from cryptography.hazmat.primitives import hmac

    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


# ---------------------------------------------------------------------------
# container structure
# ---------------------------------------------------------------------------

def _build(algo, salt, iv, rsa_wrapped, filename, tag, ct):
    name = filename.encode("utf-8")
    head = MAGIC + bytes([algo, VERSION, 0, 0]) + salt
    if rsa_wrapped:
        head += rsa_wrapped
    body = iv + struct.pack("<I", len(name)) + name + tag + ct
    return head + body


def _parse(container):
    if len(container) < 24 or container[:4] != MAGIC:
        raise SeuFormatError("E_FORMAT: not a SEU1 container")
    algo = container[4]
    version = container[5]
    if version != VERSION:
        raise SeuFormatError("E_FORMAT: unsupported container version")
    salt = container[8:24]
    pos = 24
    if algo == ALGO_RSA:
        rsa_wrapped = container[pos:pos + 512]
        pos += 512
    else:
        rsa_wrapped = None
    iv = container[pos:pos + 16]
    pos += 16
    if len(container) < pos + 4:
        raise SeuFormatError("E_FORMAT: truncated container")
    name_len = struct.unpack("<I", container[pos:pos + 4])[0]
    pos += 4
    if not 0 <= name_len <= 1024 or len(container) < pos + name_len:
        raise SeuFormatError("E_FORMAT: bad filename field")
    name = container[pos:pos + name_len].decode("utf-8", "replace")
    pos += name_len
    tag_len = 16 if algo in (ALGO_GCM, ALGO_CHACHA, ALGO_RSA) else 32
    tag = container[pos:pos + tag_len]
    pos += tag_len
    ct = container[pos:]
    return {
        "algo": algo,
        "salt": salt,
        "iv": iv,
        "rsa_wrapped": rsa_wrapped,
        "name": name,
        "tag": tag,
        "ct": ct,
    }


def detect_algo(container):
    if len(container) < 8 or container[:4] != MAGIC:
        return None
    return ALGO_NAMES.get(container[4], None)


def inspect(container):
    parsed = _parse(container)
    return {
        "algorithm": ALGO_NAMES.get(parsed["algo"], "UNKNOWN"),
        "filename": parsed["name"],
    }


# ---------------------------------------------------------------------------
# per-algorithm primitives
# ---------------------------------------------------------------------------

def _gcm_encrypt(key32, nonce, data):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(key32).encrypt(nonce[:12], data, None)


def _gcm_decrypt(key32, nonce, ct, tag):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        return AESGCM(key32).decrypt(nonce[:12], ct + tag, None)
    except InvalidTag:
        raise SeuError("E_INTEGRITY_FAIL: authentication tag verification failed")


def _chacha_encrypt(key32, nonce, data):
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    return ChaCha20Poly1305(key32).encrypt(nonce[:12], data, None)


def _chacha_decrypt(key32, nonce, ct, tag):
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    try:
        return ChaCha20Poly1305(key32).decrypt(nonce[:12], ct + tag, None)
    except InvalidTag:
        raise SeuError("E_INTEGRITY_FAIL: authentication tag verification failed")


def _cbc_encrypt(key32, iv, data):
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    enc = Cipher(ciph.AES(key32), modes.CBC(iv)).encryptor()
    return enc.update(padded) + enc.finalize()


def _cbc_decrypt(key32, iv, ct):
    dec = Cipher(ciph.AES(key32), modes.CBC(iv)).decryptor()
    padded = dec.update(ct) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def _rsa_wrap(public_key, data_key):
    return public_key.encrypt(
        data_key,
        asym_padding.OAEP(mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                          algorithm=hashes.SHA256(), label=None),
    )


def _rsa_unwrap(private_key, wrapped):
    try:
        return private_key.decrypt(
            wrapped,
            asym_padding.OAEP(mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                              algorithm=hashes.SHA256(), label=None),
        )
    except (ValueError, InvalidSignature):
        raise SeuError("E_KEY_INVALID: RSA key cannot unwrap data key")


# ---------------------------------------------------------------------------
# public API  (key: 32-byte symmetric or rsa key pair object; xor password)
# ---------------------------------------------------------------------------

def encrypt_data(data, filename="", algo=DEFAULT_ALGO, key=None, password=None):
    data_key = key if password is None else None
    rsa_wrapped = None

    if algo == ALGO_RSA:
        if key is None:
            raise SeuError("E_KEY_NOT_SET: an RSA key pair is required")
        data_key = os.urandom(32)
        rsa_wrapped = _rsa_wrap(key.public_key(), data_key)
        nonce = os.urandom(12) + b"\x00" * 4
        sealed = _gcm_encrypt(data_key, nonce, data)
        tag, ct = sealed[-16:], sealed[:-16]
        return _build(algo, b"\x00" * 16, nonce, rsa_wrapped, filename, tag, ct)

    key32 = bytes(key) if key is not None else None
    if password is not None:
        salt = os.urandom(SALT_SIZE)
        key32 = derive_key(password, salt)
    else:
        if key32 is None:
            raise SeuError("E_KEY_NOT_SET: a key or passphrase is required")
        salt = b"\x00" * 16

    if algo == ALGO_GCM:
        nonce = os.urandom(GCM_NONCE) + b"\x00" * 4
        sealed = _gcm_encrypt(key32, nonce, data)
        tag, ct = sealed[-16:], sealed[:-16]
    elif algo == ALGO_CHACHA:
        nonce = os.urandom(CHACHA_NONCE) + b"\x00" * 4
        sealed = _chacha_encrypt(key32, nonce, data)
        tag, ct = sealed[-16:], sealed[:-16]
    elif algo == ALGO_CBC:
        nonce = os.urandom(CBC_IV)
        ct = _cbc_encrypt(key32, nonce, data)
        tag = _hmac(key32, nonce + ct)
    else:
        raise SeuError("E_INTERNAL: unsupported algorithm")
    return _build(algo, salt, nonce, rsa_wrapped, filename, tag, ct)


def decrypt_data(container, key=None, password=None):
    parsed = _parse(container)
    algo = parsed["algo"]

    if algo == ALGO_RSA:
        if key is None:
            raise SeuError("E_KEY_NOT_SET: an RSA key pair is required")
        data_key = _rsa_unwrap(key, parsed["rsa_wrapped"])
        return _gcm_decrypt(data_key, parsed["iv"], parsed["ct"], parsed["tag"])

    if password is not None:
        key32 = derive_key(password, parsed["salt"])
    else:
        key32 = bytes(key)

    if algo == ALGO_GCM:
        return _gcm_decrypt(key32, parsed["iv"], parsed["ct"], parsed["tag"])
    if algo == ALGO_CHACHA:
        return _chacha_decrypt(key32, parsed["iv"], parsed["ct"], parsed["tag"])
    if algo == ALGO_CBC:
        mac = _hmac(key32, parsed["iv"] + parsed["ct"])
        if mac != parsed["tag"]:
            raise SeuError("E_INTEGRITY_FAIL: HMAC verification failed")
        try:
            return _cbc_decrypt(key32, parsed["iv"], parsed["ct"])
        except ValueError:
            raise SeuError("E_INTEGRITY_FAIL: padding error on decrypt")
    raise SeuError("E_ALGO_MISMATCH: unsupported algorithm id %d" % algo)


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------

def generate_symmetric_key():
    return os.urandom(32)


def generate_rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=4096)


def fingerprint(material):
    import hashlib

    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    if isinstance(material, rsa.RSAPrivateKey):
        raw = material.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    elif isinstance(material, rsa.RSAPublicKey):
        raw = material.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    else:
        raw = bytes(material)
    digest = hashlib.sha256(raw).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, 18, 2)) + ":..."


def encode_base64(data):
    return base64.urlsafe_b64encode(data).decode("ascii")


def decode_base64(text):
    try:
        return base64.urlsafe_b64decode(text.encode("ascii").strip())
    except Exception:
        raise SeuError("E_KEY_INVALID: not valid Base64")


# ---------------------------------------------------------------------------
# text codecs + misc UI helpers
# ---------------------------------------------------------------------------

TEXT_CODECS = ("base64", "hex", "raw")


def encode_text(data, codec="base64"):
    """Encode ciphertext bytes as printable text (base64/hex/raw latin-1)."""
    if codec == "base64":
        return base64.b64encode(data).decode("ascii")
    if codec == "hex":
        return data.hex().upper()
    if codec == "raw":
        return data.decode("latin-1")
    raise ValueError("unknown codec %r" % codec)


def decode_text(text, codec="base64"):
    if codec == "base64":
        try:
            return base64.b64decode(text.strip())
        except Exception:
            raise SeuError("E_KEY_INVALID: not valid Base64")
    if codec == "hex":
        try:
            return bytes.fromhex(text.strip())
        except ValueError:
            raise SeuError("E_KEY_INVALID: not valid hexadecimal")
    if codec == "raw":
        return text.encode("latin-1")
    raise ValueError("unknown codec %r" % codec)


def format_size(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit) if unit != "B" else "%d B" % size
        size /= 1024