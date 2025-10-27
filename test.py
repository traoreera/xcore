from auth.service import authenticate_user
from database.db import get_db
from security.hash import Hash

password_hash = authenticate_user(
    next(get_db()), "root@system.local", "password"
).password_hash

response = Hash.verify(password_hash, "password")

print(response)
