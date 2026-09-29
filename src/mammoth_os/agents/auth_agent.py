import datetime
import logging
from typing import Any, Dict, Optional

from mammoth_os.agents.base_agent import BaseAgent


class AuthAgent(BaseAgent):  # type: ignore
    """
    Handles JWT-based authentication, session management, and permission
    scope enforcement across all Mammoth OS agents and APIs.
    """

    name = "AuthAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._logger = logging.getLogger("mammoth.agent.auth")
        self._secret = "REPLACE_ME_IN_PROD"
        self._algorithm = "HS256"
        self._ttl_seconds = 3600
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_config(self, key: str, default: Any = None) -> Any:
        if hasattr(self, "router") and self.router is not None:
            config = getattr(self.router, "config", None)
            if isinstance(config, dict) and key in config:
                return config[key]
        return default

    def _resolved_secret(self) -> str:
        secret = str(self.get_config("jwt_secret") or self._secret)
        secret_bytes = secret.encode("utf-8")
        if len(secret_bytes) >= 32:
            return secret
        return (secret + ("x" * (32 - len(secret_bytes))))[:32]

    async def initialize(self) -> None:
        import jwt  # noqa: F401
        self._secret = self._resolved_secret()
        self._algorithm = str(self.get_config("algorithm") or self._algorithm)
        self._ttl_seconds = int(self.get_config("token_ttl_sec") or self._ttl_seconds)
        self._sessions = self._sessions or {}

    async def issue_token(self, user_id: str, scopes: list[str], role: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        import jwt
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required")
        if not scopes:
            scopes = ["read"]
        issued_at = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "sub": str(user_id),
            "scopes": [str(item) for item in scopes],
            "role": role or "member",
            "metadata": metadata or {},
            "iat": issued_at,
            "exp": issued_at + datetime.timedelta(seconds=self._ttl_seconds),
            "token_type": "access",
        }
        token = jwt.encode(payload, self._resolved_secret(), algorithm=self._algorithm)
        self._sessions[str(user_id)] = {
            "token": token,
            "scopes": payload["scopes"],
            "role": payload["role"],
            "issued_at": issued_at.isoformat(),
            "expires_at": payload["exp"].isoformat(),
        }
        return token

    async def validate_token(self, token: str) -> dict:
        import jwt
        if not token or not str(token).strip():
            raise ValueError("Token is required.")
        try:
            return jwt.decode(token, self._resolved_secret(), algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired.")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token.")

    async def check_permission(self, token: str, required_scope: str) -> bool:
        if not required_scope:
            return True
        try:
            claims = await self.validate_token(token)
        except ValueError:
            return False
        scopes = set(str(item) for item in claims.get("scopes", []))
        return required_scope in scopes or "*" in scopes

    async def requires_scope(self, token: str, required_scope: str) -> bool:
        return await self.check_permission(token, required_scope)

    async def run(self, payload) -> dict:
        if isinstance(payload, dict):
            action = str(payload.get("action") or "validate").strip().lower()
        else:
            action = "status"

        if action == "issue":
            user_id = str(payload.get("user_id") or "").strip()
            scopes = payload.get("scopes") or ["read"]
            role = payload.get("role")
            if not user_id:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide user_id to issue a token."}
            try:
                await self.initialize()
                token = await self.issue_token(user_id, scopes, role=role)
                return {"status": "ok", "agent": self.name, "action": "issue", "user_id": user_id, "token": token[:20] + "...", "summary": f"Token issued for {user_id}."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "error": str(exc)}

        if action == "validate":
            token = str(payload.get("token") or "").strip()
            if not token:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide a token to validate."}
            try:
                await self.initialize()
                claims = await self.validate_token(token)
                return {"status": "ok", "agent": self.name, "action": "validate", "claims": claims, "summary": "Token is valid."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "action": "validate", "error": str(exc), "summary": "Token validation failed."}

        if action == "check_permission":
            token = str(payload.get("token") or "").strip()
            scope_required = str(payload.get("scope") or "read").strip()
            try:
                await self.initialize()
                allowed = await self.check_permission(token, scope_required)
                return {"status": "ok", "agent": self.name, "action": "check_permission", "allowed": allowed, "scope": scope_required, "summary": f"Permission {'granted' if allowed else 'denied'} for scope {scope_required}."}
            except Exception as exc:
                return {"status": "error", "agent": self.name, "error": str(exc)}

        return {
            "status": "ok",
            "agent": self.name,
            "action": "status",
            "algorithm": self._algorithm,
            "ttl_seconds": self._ttl_seconds,
            "active_sessions": len(self._sessions),
            "summary": "AuthAgent is active.",
            "quality_flags": ["jwt_auth", "scope_enforcement", "session_tracking"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return None
        if getattr(event, "event_type", None) == "TOKEN_REQUEST":
            payload = getattr(event, "payload", {}) or {}
            await self.issue_token(payload.get("user_id", "guest"), payload.get("scopes", ["read"]))

    async def shutdown(self) -> None:
        self._logger.info("AuthAgent shutting down.")
