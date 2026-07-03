"""ASCII-safe console logging.

On Windows the default stdout encoding is cp1252, so print()-ing a string that
contains an emoji or arrow (from a user's message or an LLM-generated draft)
raises UnicodeEncodeError — which, inside a request handler, becomes a 500.

slog() prints normally when the terminal can handle it, and only falls back to
a replaced-character version when the stream can't encode the text, so logging
never crashes the caller.
"""
import sys


def slog(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(str(msg).encode(enc, "replace").decode(enc))
