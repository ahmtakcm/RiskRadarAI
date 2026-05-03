import hashlib

def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()
