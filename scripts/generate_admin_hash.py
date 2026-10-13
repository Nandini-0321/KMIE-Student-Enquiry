"""
Script to generate a secure Werkzeug password hash for administrator credentials.
Use this script to create the value for ADMIN_PASSWORD_HASH in .env or Render environment.

Usage:
    python scripts/generate_admin_hash.py
    python scripts/generate_admin_hash.py mysecretpassword
"""
import sys
import getpass
from werkzeug.security import generate_password_hash


def main():
    if len(sys.argv) > 1:
        plain_password = sys.argv[1]
    else:
        plain_password = getpass.getpass("Enter administrator password to hash: ")
        confirm_password = getpass.getpass("Confirm password: ")
        if plain_password != confirm_password:
            print("Error: Passwords do not match.")
            sys.exit(1)

    if not plain_password.strip():
        print("Error: Password cannot be empty.")
        sys.exit(1)

    # Use scrypt (or pbkdf2)
    hashed = generate_password_hash(plain_password, method="scrypt")
    print("\nGenerated Administrator Password Hash:")
    print("--------------------------------------------------------------------------------")
    print(hashed)
    print("--------------------------------------------------------------------------------")
    print("\nCopy and paste this value into your environment configuration:")
    print(f"ADMIN_PASSWORD_HASH={hashed}\n")


if __name__ == "__main__":
    main()
