from fastapi import Depends, HTTPException

from auth.dependencies import get_current_user


def require_admin(current_user=Depends(get_current_user)):
    roles = [r.name for r in current_user.roles]
    if "root" not in roles and "admin" not in roles and "superadmin" not in roles:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user


def require_superuser(current_user=Depends(require_admin)):
    roles = [r.name for r in current_user.roles]
    if "superadmin" not in roles:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user
