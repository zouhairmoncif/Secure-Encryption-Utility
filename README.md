#  Secure Encryption Utility

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Crypto](https://img.shields.io/badge/Crypto-AES--256--GCM-orange?style=flat-square&logo=gnuprivacyguard&logoColor=white)
![UI](https://img.shields.io/badge/UI-BIOS%20Text--Mode-grey?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

> A professional file & text encryption tool with a classic **BIOS/DOS-style** terminal interface.

---

## Features

- 🔐 **AES-256-GCM**, AES-256-CBC, ChaCha20-Poly1305, RSA-4096 encryption
- 📁 File encryption & decryption with integrity verification
- 📝 Text encryption / decryption with clipboard support
- 🗝️ Secure key generation, storage, import & export
- 🧹 Secure file deletion (DoD 5220.22-M)
- 📜 Operation history log
- 💾 Encrypted key store at rest
- 🖥️ Authentic BIOS-style text-mode UI — full keyboard navigation

---

## Requirements

```
Python 3.10+
cryptography >= 42.0
```

---

## Install & Run

```bash
git clone https://github.com/your-username/secure-encryption-utility.git
cd secure-encryption-utility
pip install -r requirements.txt
python main.py
```

---

## Usage

Navigate with **↑ ↓ arrow keys**, confirm with **Enter**, go back with **Esc**.

| Key | Action |
|-----|--------|
| `↑ ↓` | Navigate menu |
| `Enter` | Select |
| `Esc` | Back |
| `F1` | Help |
| `F10` | Exit |

---

## Supported Algorithms

| Algorithm | Type | Key Size |
|-----------|------|----------|
| AES-256-GCM | Symmetric | 256-bit |
| AES-256-CBC + HMAC | Symmetric | 256-bit |
| ChaCha20-Poly1305 | Symmetric | 256-bit |
| RSA-4096 + AES-256 | Asymmetric | 4096-bit |

---

## License

MIT © [Moncif ZouhaiR]