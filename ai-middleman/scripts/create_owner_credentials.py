"""Print secure owner-session settings for ai-middleman/.env.

Run interactively; this script never writes a file and never sends data over
the network. Paste only the two printed settings into an untracked .env file.
"""
from getpass import getpass
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import hash_password


def main() -> int:
    password = getpass("Choose a long owner-console password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords did not match.", file=sys.stderr)
        return 1
    if len(password) < 16:
        print("Use at least 16 characters.", file=sys.stderr)
        return 1
    print("\nPaste these into ai-middleman/.env (do not commit that file):")
    print("ADMIN_PASSWORD_HASH=" + hash_password(password))
    print("SESSION_SIGNING_SECRET=" + secrets.token_urlsafe(48))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
