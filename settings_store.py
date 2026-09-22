"""Application settings persistence for the Secure Encryption Utility."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".encryption_utility"

DEFAULTS = {
    "algo": "AES-256-GCM",
    "output_naming": "auto",
    "secure_delete": "dod",
    "wipe_source_after_encrypt": False,
    "date_format": "iso",
    "clear_clipboard": True,
    "crt_scanlines": True,
    "crt_phosphor": True,
    "crt_curvature": True,
}


class Settings:
    def __init__(self):
        self._d = dict(DEFAULTS)
        self._load()

    def _path(self):
        return CONFIG_DIR / "settings.json"

    def _load(self):
        path = self._path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for key, val in DEFAULTS.items():
                    if key in data:
                        self._d[key] = data[key]
            except (OSError, ValueError):
                pass

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._path().write_text(
                json.dumps(self._d, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get(self, key):
        return self._d.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._d[key] = value
        self.save()