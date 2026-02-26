"""
users_plugin/src/main.py
━━━━━━━━━━━━━━━━━━━━━━━━
Plugin de gestion des utilisateurs — exemple complet xcore v2.

Démontre :
  ┌─────────────────────────────────────────────────────┐
  │  1. Héritage TrustedBase + RoutedPlugin             │
  │  2. Routes HTTP via @route (REST complet)           │
  │  3. Actions IPC via @action (canal JSON)            │
  │  4. Accès BDD via self.get_service("db")            │
  │  5. Cache avec get_or_set()                         │
  │  6. Extension email via self.get_service("ext.email")│
  │  7. Hooks cycle de vie (on_load, on_unload)         │
  │  8. @validate_payload sur les entrées               │
  │  9. @require_service pour les guards                │
  └─────────────────────────────────────────────────────┘

Routes HTTP montées automatiquement sous /plugins/users_plugin/ :
  GET    /users/             → liste paginée
  POST   /users/             → créer un utilisateur
  GET    /users/{user_id}    → récupérer un utilisateur
  PUT    /users/{user_id}    → modifier un utilisateur
  DELETE /users/{user_id}    → supprimer un utilisateur
  GET    /users/{user_id}/avatar → avatar de l'utilisateur

Actions IPC (POST /app/users_plugin/<action>) :
  create_user  → {email, username, password}
  get_user     → {user_id}
  list_users   → {page?, page_size?, search?}
  delete_user  → {user_id}
  ping         → {} → health check rapide
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, field_validator

from xcore.sdk import (
    AutoDispatchMixin,
    RoutedPlugin,
    TrustedBase,
    action,
    error,
    ok,
    require_service,
    route,
    validate_payload,
)


class Route(RoutedPlugin, AutoDispatchMixin):



    @action("users")
    @staticmethod
    async def list_users(page: int = 1, page_size: int = 10, search: str | None = None):
        return {}
    @route("/users", method="GET")
    async def get_users(self,page: int = 1, page_size: int = 10, search: str | None = None):
        return {}


class Plugin(Route, TrustedBase):
    
    def __init__(self) -> None:
        super().__init__()
    

    async def on_load(self) -> None:
        
        session = self.get_service("async_default")
        #session.close()
        
        return await super().on_load()
