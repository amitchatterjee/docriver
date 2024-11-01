import asyncio
from okta_jwt_verifier import BaseJWTVerifier
from okta_jwt_verifier.exceptions import JWTValidationException

class OktaTokenValidator:
    def __init__(self, okta_url, okta_aud) -> None:
        self.okta_url = okta_url
        self.okta_aud = okta_aud
        self.loop = asyncio.get_event_loop()
        self.jwt_verifier = BaseJWTVerifier(issuer=okta_url, audience=okta_aud)

    async def verify_sync(self, token):
        await self.jwt_verifier.verify_access_token(token)

    def verify(self, token):
        self.loop.run_until_complete(self.verify_sync(token))
        return self.jwt_verifier.parse_token(token)