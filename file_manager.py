import os

def read_file(filepath: str) -> bytes:
    """Reads and returns the contents of a file as bytes."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    # Note: Loading entire files into memory works fine for most files,
    # but could cause MemoryErrors for files > 1-2 GB on standard machines.
    with open(filepath, 'rb') as f:
        return f.read()

def write_file(filepath: str, data: bytes) -> None:
    """Writes bytes to a file."""
    with open(filepath, 'wb') as f:
        f.write(data)

def get_default_output_path(input_path: str, action: str) -> str:
    """Generates a logical default output filename based on the action."""
    if action == "encrypt":
        return input_path + ".enc"
    elif action == "decrypt":
        if input_path.endswith(".enc"):
            return input_path[:-4]  # Remove .enc extension
        else:
            return input_path + ".dec" # Fallback if extension isn't .enc
    return input_path