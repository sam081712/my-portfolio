#!/usr/bin/env python3
"""Usage: python scripts/hash_password.py "YourNewPassword" """
import sys
import bcrypt


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/hash_password.py "YourPassword"', file=sys.stderr)
        sys.exit(1)
    pwd = sys.argv[1].encode("utf-8")
    hashed = bcrypt.hashpw(pwd, bcrypt.gensalt(10))
    print(hashed.decode("utf-8"))


if __name__ == "__main__":
    main()
