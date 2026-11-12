"""Authentication: user accounts, password login and server-side sessions.

`models.py` holds the tables, `passwords.py` the pwdlib (argon2) wrapper,
`sessions.py` the opaque-token session store, `deps.py` the `current_user` and
`require_admin` FastAPI dependencies, `cleanup.py` the scheduled expired-session
sweep and `__main__.py` the operator CLI (`python -m app.auth`). The HTTP
endpoints live in `app/api/auth.py`.
"""
