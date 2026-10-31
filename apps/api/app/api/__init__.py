"""HTTP API for the duty manager dashboard.

Limits: runs live in memory in one process, keyed by run ID, and used sign-off
tokens are per process. A restart forgets both; more than one worker would not
share them. There is no auth and no database.
"""
