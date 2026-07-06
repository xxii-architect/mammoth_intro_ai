class AuthAgent(BaseAgent): # type: ignore
    """
    Handles JWT-based authentication, session management, and permission
    scope enforcement across all Mammoth OS agents and APIs.
    """

    async def initialize(self) -> None:
        import jwt
        self._secret = self.get_config("jwt_secret") or "REPLACE_ME_IN_PROD"
        self._algorithm = self.get_config("algorithm") or "HS256"
        self._ttl_seconds = self.get_config("token_ttl_sec") or 3600
        self._sessions: dict[str, dict] = {}

    async def issue_token(self, user_id: str, scopes: list[str]) -> str:
        import jwt, datetime
        payload = {
            "sub": user_id,
            "scopes": scopes,
            "iat": datetime.datetime.utcnow(),
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=self._ttl_seconds),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    async def validate_token(self, token: str) -> dict:
        import jwt
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired.")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token.")

    async def check_permission(self, token: str, required_scope: str) -> bool:
        claims = await self.validate_token(token)
        return required_scope in claims.get("scopes", [])

    async def process(self, event: "MammothEvent") -> None: # type: ignore
        pass

    async def shutdown(self) -> None:
        self.log("INFO", "AuthAgent shutting down.")