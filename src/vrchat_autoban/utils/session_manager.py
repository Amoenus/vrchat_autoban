from vrchat_autoban.utils.interfaces import FileHandler


from loguru import logger
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import ApiException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode


import json
from http.cookiejar import Cookie
from typing import Optional, Dict


class SessionManager:
    def __init__(
        self, auth_api: authentication_api.AuthenticationApi, file_handler: FileHandler
    ):
        self.auth_api = auth_api
        self.file_handler = file_handler
        self.session_file = "vrchat_session.json"

    async def load_session(self) -> Optional[Dict[str, Dict[str, str]]]:
        try:
            content = await self.file_handler.read_file(self.session_file)
            return json.loads(content)
        except FileNotFoundError:
            logger.info("No existing session found.")
            return None
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.session_file}'. Starting with a fresh session."
            )
            return None

    async def save_session(self, session_data: Dict[str, Dict[str, str]]):
        content = json.dumps(session_data, indent=2)
        await self.file_handler.write_file(self.session_file, content)

    def _cookie_to_dict(self, cookie: Cookie) -> Dict[str, str]:
        return {
            "value": str(cookie.value) if cookie.value is not None else "",
            "expires": str(cookie.expires),
            "domain": cookie.domain,
            "path": cookie.path,
        }

    def _dict_to_cookie(self, name: str, cookie_dict: Dict[str, str]) -> Cookie:
        return Cookie(
            version=0,
            name=name,
            value=cookie_dict["value"],
            port=None,
            port_specified=False,
            domain=cookie_dict["domain"],
            domain_specified=False,
            domain_initial_dot=False,
            path=cookie_dict["path"],
            path_specified=True,
            secure=False,
            expires=int(cookie_dict["expires"]),
            discard=False,
            comment=None,
            comment_url=None,
            rest={"HttpOnly": "", "SameSite": "Lax"},
            rfc2109=False,
        )

    async def authenticate(self):
        session = await self.load_session()

        if session and "auth" in session and "twoFactorAuth" in session:
            try:
                auth_cookie = self._dict_to_cookie("auth", session["auth"])
                two_factor_cookie = self._dict_to_cookie(
                    "twoFactorAuth", session["twoFactorAuth"]
                )

                self.auth_api.api_client.rest_client.cookie_jar.set_cookie(auth_cookie)
                self.auth_api.api_client.rest_client.cookie_jar.set_cookie(
                    two_factor_cookie
                )

                current_user = self.auth_api.get_current_user()
                logger.info(
                    f"Successfully authenticated using stored session for: {current_user.display_name}"
                )
                return
            except ApiException:
                logger.info("Stored session expired or invalid. Reauthenticating...")

        try:
            current_user = self.auth_api.get_current_user()
            logger.info(f"Logged in as: {current_user.display_name}")
        except ApiException as e:
            if e.status == 200:
                if "Email 2 Factor Authentication" in str(e):
                    await self._handle_email_2fa()
                elif "2 Factor Authentication" in str(e):
                    await self._handle_2fa()
                current_user = self.auth_api.get_current_user()
            else:
                raise

        # Save the new session
        cookie_jar = self.auth_api.api_client.rest_client.cookie_jar
        vrchat_cookies = cookie_jar._cookies.get("vrchat.com", {}).get("/", {})

        auth_cookie = vrchat_cookies.get("auth")
        two_factor_cookie = vrchat_cookies.get("twoFactorAuth")

        if auth_cookie and two_factor_cookie:
            session_data = {
                "auth": self._cookie_to_dict(auth_cookie),
                "twoFactorAuth": self._cookie_to_dict(two_factor_cookie),
            }
            await self.save_session(session_data)
        else:
            logger.error(
                "Failed to obtain authentication cookies after authentication."
            )

    async def _handle_email_2fa(self):
        code = input("Email 2FA Code: ")
        self.auth_api.verify2_fa_email_code(
            two_factor_email_code=TwoFactorEmailCode(code=code)
        )

    async def _handle_2fa(self):
        code = input("2FA Code: ")
        self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code=code))
