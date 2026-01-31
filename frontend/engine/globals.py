import hashlib
import time

from starlette.requests import Request


def generate_csrf_token(request: Request = None):
    """Generate CSRF token"""
    if request and hasattr(request.state, "csrf_token"):
        return request.state.csrf_token
    return f"<input type='hidden' name='csrf_token' value='{hashlib.sha256(f'{time.time()}'.encode()).hexdigest()}'>"


def paginate(items: list, page: int = 1, per_page: int = 10):
    """Paginate a list of items"""
    total = len(items)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
    }


def breadcrumbs(request: Request = None):
    """Generate breadcrumbs from URL path"""
    if not request:
        return []

    path = request.url.path
    parts = [p for p in path.split("/") if p]

    crumbs = [{"name": "Accueil", "url": "/"}]
    current_path = ""

    for part in parts:
        current_path += f"/{part}"
        crumbs.append({"name": part.replace("-", " ").title(), "url": current_path})

    return crumbs
