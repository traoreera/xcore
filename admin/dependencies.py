from fastapi import Depends, HTTPException, status
from auth.dependencies import get_current_user

def require_admin(current_user=Depends(get_current_user)):
    roles = [r.name for r in current_user.roles]
    if "admin" not in roles and "superadmin" not in roles:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user
