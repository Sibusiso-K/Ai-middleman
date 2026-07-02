"""Test what exceptions produce empty str()."""
import httpx
import asyncio

# Test httpx.RemoteProtocolError
try:
    raise httpx.RemoteProtocolError('')
except Exception as e:
    print(f'RemoteProtocolError(empty): type={type(e).__name__}, str={str(e)!r}, repr={e!r}')

# Test asyncio.CancelledError
try:
    raise asyncio.CancelledError()
except Exception as e:
    print(f'CancelledError: type={type(e).__name__}, str={str(e)!r}, repr={e!r}')

# Test generic Exception with no args
try:
    raise Exception()
except Exception as e:
    print(f'Exception(): type={type(e).__name__}, str={str(e)!r}, repr={e!r}')

# Test httpx.ReadTimeout
try:
    raise httpx.ReadTimeout("")
except Exception as e:
    print(f'ReadTimeout(empty): type={type(e).__name__}, str={str(e)!r}, repr={e!r}')