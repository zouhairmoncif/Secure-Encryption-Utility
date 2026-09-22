import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Constants
SALT_SIZE = 16
ITERATIONS = 480000 # Secure iteration count for modern standards

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derives a secure cryptographic key from a password and salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    # Fernet requires a url-safe base64 encoded 32-byte key
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))

def encrypt_data(data: bytes, password: str) -> bytes:
    """
    Encrypts bytes using a password.
    Returns: salt + encrypted_data
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(password, salt)
    f = Fernet(key)
    encrypted_data = f.encrypt(data)
    
    # Prepend the salt to the ciphertext so we can retrieve it for decryption
    return salt + encrypted_data

def decrypt_data(encrypted_content: bytes, password: str) -> bytes:
    """
    Decrypts bytes using a password.
    Extracts the salt from the first 16 bytes.
    """
    if len(encrypted_content) <= SALT_SIZE:
        raise ValueError("Invalid encrypted file format. File is too small.")
    
    salt = encrypted_content[:SALT_SIZE]
    encrypted_data = encrypted_content[SALT_SIZE:]
    
    key = _derive_key(password, salt)
    f = Fernet(key)
    
    try:
        decrypted_data = f.decrypt(encrypted_data)
        return decrypted_data
    except InvalidToken:
        # InvalidToken is thrown when the key (password) is wrong or data is corrupted
        raise ValueError("Incorrect password or corrupted file.")