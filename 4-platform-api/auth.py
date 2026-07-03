"""OAuth2 (JWT) issuance + RBAC for the Platform API (task 4.4).

Tenant admins authenticate their API key for a short-lived JWT that carries a
role + permissions. Permissions come from config/security/compliance.yaml
(rbac.roles). Machine clients may keep using the raw X-API-Key header.
"""

from __future__ import annotations

import os
import time

import jwt

JWT_SECRET = os.environ.get("JWT_SECRET", "speedflow-dev-jwt-secret-change-me")
JWT_ALG = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", "3600"))

# Default RBAC role→permissions (mirrors config/security/compliance.yaml).
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": ["*"],
    "operator": ["deploy", "scale", "view_metrics"],
    "analyst": ["read_data", "query_dashboard", "view_metrics"],
    "api_consumer": ["marketplace_read", "marketplace_order"],
}


def load_role_permissions(compliance_path: str | None = None) -> dict[str, list[str]]:
    path = compliance_path or os.environ.get("COMPLIANCE_CONFIG", "/app/config/security/compliance.yaml")
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        roles = data.get("rbac", {}).get("roles", {})
        parsed = {name: (spec or {}).get("permissions", []) for name, spec in roles.items()}
        return parsed or DEFAULT_ROLE_PERMISSIONS
    except Exception:
        return DEFAULT_ROLE_PERMISSIONS


ROLE_PERMISSIONS = load_role_permissions()


def permissions_for(role: str) -> list[str]:
    return ROLE_PERMISSIONS.get(role, [])


def issue_token(tenant_id: str, role: str, plan: str) -> str:
    now = int(time.time())
    payload = {
        "sub": tenant_id,
        "role": role,
        "plan": plan,
        "permissions": permissions_for(role),
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
        "iss": "speedflow-platform",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], options={"require": ["exp", "sub"]})


def has_permission(permissions: list[str], required: str) -> bool:
    return "*" in permissions or required in permissions
