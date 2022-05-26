import hashlib
import os


class Util:
    def generate_salt():
        return os.urandom(16)

    def generate_hash(password, salt):
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000,
            dklen=16
        )
        return key

    def strong_password(pwd):
        if (len(pwd) < 8):
            print("Password should have at least 8 characters")
            return False

        digit = False
        symbol = False
        upper = False
        lower = False
        alpha = False

        for c in pwd:
            if c.isdigit():
                digit = True
            if c in ['!', '@', '#', '?']:
                symbol = True
            if c.isupper():
                upper = True
            if c.islower():
                lower = True
            if c.isalpha():
                alpha = True

        if (not (lower and upper)):
            if (lower):
                print("Lower")
            if (upper):
                print("Upper")
            print("Password should have a mixture of both uppercase and lowercase letters.")
            return False

        if (not (alpha and digit)):
            print("Password should have a mixture of letters and numbers.")
            return False

        if (not symbol):
            print("Password should include at least one special character, from '!', '@', '#', '?'.")
            return False

        return True
