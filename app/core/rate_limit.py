"""Rate limiting for brute-forceable endpoints.

Per-client-IP, in-memory (fine for a single-process deployment; swap the
storage_uri for a Redis-backed one behind a load balancer — see slowapi's
docs). Applied narrowly to /auth/login and /auth/refresh, not globally:
those are the two endpoints an attacker can hammer without already holding
a valid credential.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
