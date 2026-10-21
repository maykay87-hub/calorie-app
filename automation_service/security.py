import hashlib
import hmac
import secrets
import re

def email_key(email):
    email = email.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Enter a valid email address.')
    return email

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('Use a password of 12–128 characters.')
    salt = secrets.token_hex(16)
    result = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${result}'

def password_matches(password, stored):
    try:
        if not isinstance(password,str) or len(password) > 128: return False
        _, salt, expected = (stored or 'scrypt$' + '00'*16 + '$' + '00'*64).split('$')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError): return False

def random_token(): return secrets.token_urlsafe(32)
