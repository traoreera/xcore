from fastapi import Depends, HTTPException
from auth.dependencies import get_current_user


def require_admin(current_user=Depends(get_current_user)):
    """Dependency to require admin privileges for a route."""
    roles = [r.name for r in current_user.roles]
    user_requiered = ["root", "admin", "superadmin"]
    if  all(role in roles for role in user_requiered):
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user


def require_superuser(current_user=Depends(require_admin)):
    """Dependency to require superadmin privileges for a route."""
    if "superadmin" not in [r.name for r in current_user.roles]: 
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user
