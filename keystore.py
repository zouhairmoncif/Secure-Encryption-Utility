"""Encrypted-at-rest key store for the Secure Encryption Utility.

Business layer. Reuses the preserved `encryption.py` Fernet engine to
encrypt the whole key store JSON with a locally generated master key
(32 random bytes stored in <user home>/.encryption_utility/master.key).
The master key never leaves the machine and the key material stored in
keys.enc is therefore encrypted at rest.
"""

import base64
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import encryption
import seu_crypto

CONFIG_DIR = Path.home() / ".encryption_utility"
MASTER_KEY_PATH = CONFIG_DIR / "master.key"
KEYS_PATH = CONFIG_DIR / "keys.enc"

MAX_KEYS = 32


class KeyStoreError(Exception):
    pass


class KeyStore:
    def __init__(self):
        self._keys = []
        self._ensure_master()
        self._load()

    # ----- master key -----

    def _ensure_master(self):
        try:
            if not MASTER_KEY_PATH.exists():
                MASTER_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
                with os.fdopen(
                    os.open(str(MASTER_KEY_PATH), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                    "wb",
                ) as fh:
                    fh.write(os.urandom(32))
        except (OSError, ValueError):
            raise KeyStoreError("E_DIR_UNWRITABLE: cannot create key store directory")

    def _master_passphrase(self):
        try:
            with open(MASTER_KEY_PATH, "rb") as fh:
                return fh.read(1024).hex()
        except (OSError, ValueError):
            raise KeyStoreError("E_KEY_INVALID: master key unreadable")

    # ----- persistence -----

    def exists(self):
        return KEYS_PATH.exists()

    def _load(self):
        if not KEYS_PATH.exists():
            self._save()
            return
        try:
            blob = KEYS_PATH.read_bytes()
            plain = encryption.decrypt_data(blob, self._master_passphrase())
        except (OSError, ValueError) as exc:
            raise KeyStoreError("E_INTEGRITY_FAIL: key store decrypt failed") from exc
        try:
            data = json.loads(plain.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise KeyStoreError("E_FORMAT: key store is not valid JSON") from exc
        self._keys = data.get("keys", [])
        self._keys = self._keys[-MAX_KEYS:]

    def _save(self):
        try:
            blob = json.dumps({"version": 1, "keys": self._keys}).encode("utf-8")
            enc = encryption.encrypt_data(blob, self._master_passphrase())
            tmp = KEYS_PATH.with_suffix(".tmp")
            tmp.write_bytes(enc)
            tmp.replace(KEYS_PATH)
        except (OSError, ValueError) as exc:
            raise KeyStoreError("E_DIR_UNWRITABLE: cannot persist key store") from exc

    # ----- queries -----

    def list(self):
        return list(self._keys)

    def count(self):
        return len(self._keys)

    def get_active(self):
        for rec in self._keys:
            if rec.get("active"):
                return rec
        return None

    def find(self, key_id):
        for rec in self._keys:
            if rec["id"] == key_id:
                return rec
        return None

    def key_material(self, rec):
        """Return key bytes (symmetric) or an rsa key object."""
        if rec["kind"] == "rsa":
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                PrivateFormat,
                NoEncryption,
                load_pem_private_key,
            )

            try:
                return load_pem_private_key(rec["material"].encode("ascii"), None)
            except (ValueError, TypeError) as exc:
                raise KeyStoreError("E_KEY_INVALID: stored RSA key unreadable") from exc
        try:
            return base64.b64decode(rec["material"])
        except (ValueError, TypeError) as exc:
            raise KeyStoreError("E_KEY_INVALID: stored symmetric key unreadable") from exc

    # ----- mutations -----

    def _bump(self, rec):
        rec["uses"] = rec.get("uses", 0) + 1
        rec["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()

    def add_symmetric(self, name, algo):
        self._check_space()
        material = seu_crypto.generate_symmetric_key()
        rec = self._make_record(name, algo, "sym", base64.b64encode(material).decode("ascii"))
        self._keys.append(rec)
        self._save()
        return rec

    def add_rsa(self, name, algo="RSA-4096 + AES-256"):
        self._check_space()
        key = seu_crypto.generate_rsa_key()
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )

        pem = key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode("ascii")
        rec = self._make_record(name, algo, "rsa", pem)
        self._keys.append(rec)
        self._save()
        return rec

    def _check_space(self):
        if len(self._keys) >= MAX_KEYS:
            raise KeyStoreError("E_DISK_FULL: key store is full (%d keys)" % MAX_KEYS)

    def _make_record(self, name, algo, kind, material):
        fp = seu_crypto.fingerprint(
            base64.b64decode(material) if kind == "sym" else material.encode("ascii")
        )
        return {
            "id": uuid.uuid4().hex[:8].upper(),
            "name": (name or "Untitled").strip()[:40],
            "algo": algo,
            "kind": kind,
            "material": material,
            "fingerprint": fp,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "uses": 0,
            "last_used": "-",
            "active": False,
        }

    def set_active(self, key_id):
        found = False
        for rec in self._keys:
            if rec["id"] == key_id:
                rec["active"] = True
                found = True
            else:
                rec["active"] = False
        if not found:
            raise KeyStoreError("E_KEY_INVALID: key id not found")
        self._save()

    def rename(self, key_id, new_name):
        rec = self.find(key_id)
        if rec is None:
            raise KeyStoreError("E_KEY_INVALID: key id not found")
        rec["name"] = new_name.strip()[:40]
        self._save()

    def delete(self, key_id):
        before = len(self._keys)
        rec = self.find(key_id)
        if rec is None:
            raise KeyStoreError("E_KEY_INVALID: key id not found")
        self._keys = [r for r in self._keys if r["id"] != key_id]
        if rec.get("active") and self._keys:
            self._keys[0]["active"] = True
        if len(self._keys) == before:
            raise KeyStoreError("E_KEY_INVALID: key id not found")
        # zero the material out of memory best-effort
        rec["material"] = ""
        self._save()

    def mark_used(self, key_id):
        rec = self.find(key_id)
        if rec is not None:
            self._bump(rec)
            return rec
        return None

    # ----- import / export -----

    def export(self, key_id):
        rec = self.find(key_id)
        if rec is None:
            raise KeyStoreError("E_KEY_INVALID: key id not found")
        return {
            "id": rec["id"],
            "name": rec["name"],
            "algo": rec["algo"],
            "kind": rec["kind"],
            "text": rec["material"],
            "fingerprint": rec["fingerprint"],
            "created": rec["created"],
        }

    def import_key(self, name, algo, text):
        self._check_space()
        text = text.strip()
        if "-----BEGIN" in text:
            decode_pem(text)
            kind = "rsa"
            material = text
        else:
            decoded = seu_crypto.decode_base64(text)
            if len(decoded) != 32:
                raise KeyStoreError("E_KEY_INVALID: symmetric keys must be 256-bit (32 bytes)")
            kind = "sym"
            material = base64.b64encode(decoded).decode("ascii")
        rec = self._make_record(name, algo, kind, material)
        self._keys.append(rec)
        self._save()
        return rec


def decode_pem(text):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    try:
        return load_pem_private_key(text.encode("ascii"), None)
    except (ValueError, TypeError) as exc:
        raise KeyStoreError("E_KEY_INVALID: not a valid PEM private key") from exc