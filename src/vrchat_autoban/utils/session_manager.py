import json
from http.cookiejar import Cookie, CookieJar
from pathlib import Path  # Added
from typing import Dict, Optional

from loguru import logger
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import ApiException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode

from vrchat_autoban.utils.interfaces import FileHandler


class SessionManager:
    def __init__(
        self,
        auth_api: authentication_api.AuthenticationApi,
        file_handler: FileHandler,
        session_file_path: Path,  # Modified
    ):
        self.auth_api = auth_api
        self.file_handler = file_handler
        self.session_file: Path = session_file_path  # Modified

    async def load_session(self) -> Optional[Dict[str, Dict[str, str]]]:
        try:
            content = await self.file_handler.read_file(
                str(self.session_file)
            )  # Modified
            return json.loads(content)
        except FileNotFoundError:
            logger.info(f"No existing session found at {self.session_file}.")
            return None
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse session file '{self.session_file}'. Starting with a fresh session."
            )
            return None
        except Exception as e:
            logger.error(
                f"Error loading session file '{self.session_file}': {e}. Starting fresh."
            )
            return None

    async def save_session(self, session_data: Dict[str, Dict[str, str]]):
        try:
            content = json.dumps(session_data, indent=2)
            await self.file_handler.write_file(
                str(self.session_file), content
            )  # Modified
            logger.info(f"Session saved to {self.session_file}")
        except Exception as e:
            logger.error(f"Failed to save session to {self.session_file}: {e}")

    def _convert_cookie_to_dict(self, cookie: Cookie) -> Dict[str, str]:
        return {
            "value": str(cookie.value) if cookie.value is not None else "",
            "expires": (
                str(cookie.expires) if cookie.expires is not None else "0"
            ),  # Ensure expires is always a string
            "domain": cookie.domain or "",  # Ensure domain is not None
            "path": cookie.path or "/",  # Ensure path is not None
        }

    def _convert_dict_to_cookie(self, name: str, cookie_dict: Dict[str, str]) -> Cookie:
        try:
            expires_val = int(cookie_dict.get("expires", "0") or "0")
        except (ValueError, TypeError):
            expires_val = 0  # Default if conversion fails
            logger.warning(f"Invalid 'expires' value for cookie '{name}', using 0.")

        return Cookie(
            version=0,
            name=name,
            value=cookie_dict.get("value", ""),
            port=None,
            port_specified=False,
            domain=cookie_dict.get("domain", ""),
            domain_specified=bool(cookie_dict.get("domain")),  # Set based on presence
            domain_initial_dot=cookie_dict.get("domain", "").startswith(
                "."
            ),  # Set based on domain
            path=cookie_dict.get("path", "/"),
            path_specified=True,
            secure=False,  # Assuming False, adjust if API requires HTTPS-only cookies
            expires=expires_val,
            discard=False,
            comment=None,
            comment_url=None,
            rest={
                "HttpOnly": "",
                "SameSite": "Lax",
            },
            rfc2109=False,
        )

    async def authenticate_user(self):
        session = await self.load_session()

        if session and "auth" in session and "twoFactorAuth" in session:
            try:
                auth_cookie_dict = session.get("auth")
                two_factor_cookie_dict = session.get("twoFactorAuth")

                if auth_cookie_dict and two_factor_cookie_dict:
                    auth_cookie = self._convert_dict_to_cookie("auth", auth_cookie_dict)
                    two_factor_cookie = self._convert_dict_to_cookie(
                        "twoFactorAuth", two_factor_cookie_dict
                    )

                    # Ensure cookie_jar exists
                    if self.auth_api.api_client.rest_client.cookie_jar is None:
                        self.auth_api.api_client.rest_client.cookie_jar = CookieJar()

                    self.auth_api.api_client.rest_client.cookie_jar.set_cookie(
                        auth_cookie
                    )
                    self.auth_api.api_client.rest_client.cookie_jar.set_cookie(
                        two_factor_cookie
                    )

                    current_user = self.auth_api.get_current_user()
                    logger.info(
                        f"Successfully authenticated using stored session for: {current_user.display_name}"
                    )
                    return
                else:
                    logger.info(
                        "Stored session data is incomplete. Reauthenticating..."
                    )

            except ApiException:
                logger.info("Stored session expired or invalid. Reauthenticating...")
            except Exception as e:
                logger.error(
                    f"Error processing stored session: {e}. Reauthenticating..."
                )

        try:
            current_user = (
                self.auth_api.get_current_user()
            )  # This initiates login if not authed
            logger.info(f"Logged in as: {current_user.display_name}")
        except ApiException as e:
            if e.status == 200 and e.body:  # Successful response but requires 2FA
                response_body = json.loads(e.body)
                if response_body.get("requiresTwoFactorAuth"):
                    auth_types = response_body.get("requiresTwoFactorAuth", [])
                    if "emailOtp" in auth_types:
                        logger.info("Email 2 Factor Authentication required.")
                        await self._handle_email_2fa()
                    elif (
                        "totp" in auth_types
                    ):  # Typically 'otp' or 'totp' for authenticator apps
                        logger.info(
                            "Authenticator App 2 Factor Authentication required."
                        )
                        await self._handle_2fa()
                    else:  # Unknown 2FA method
                        logger.error(
                            f"Unknown 2FA methods required: {auth_types}. Cannot proceed."
                        )
                        raise
                    current_user = (
                        self.auth_api.get_current_user()
                    )  # Verify login after 2FA
                    logger.info(
                        f"Successfully logged in as: {current_user.display_name} after 2FA."
                    )
                else:  # Other 200 OK responses that are not user objects
                    logger.error(
                        f"Unexpected API response during login (Status 200 but not user object or 2FA prompt): {e.body}"
                    )
                    raise
            else:  # Other API errors
                logger.error(f"API Exception during login: {e.status} - {e.reason}")
                logger.error(f"Response body: {e.body}")
                raise

        # Save the new session
        cookie_jar: Optional[CookieJar] = (
            self.auth_api.api_client.rest_client.cookie_jar
        )

        if cookie_jar:
            vrchat_cookies = {}
            for _domain_cookies in cookie_jar:
                for cookie in cookie_jar:
                    if cookie.domain.endswith("vrchat.com"):
                        vrchat_cookies[cookie.name] = cookie

            auth_cookie_obj = vrchat_cookies.get("auth")
            two_factor_cookie_obj = vrchat_cookies.get("twoFactorAuth")

            if auth_cookie_obj and two_factor_cookie_obj:
                session_data = {
                    "auth": self._convert_cookie_to_dict(auth_cookie_obj),
                    "twoFactorAuth": self._convert_cookie_to_dict(
                        two_factor_cookie_obj
                    ),
                }
                await self.save_session(session_data)
            else:
                logger.warning(  # Changed to warning as it might not be critical if already logged in
                    "Failed to obtain one or both authentication cookies (auth, twoFactorAuth) for session saving."
                )
        else:
            logger.warning(
                "CookieJar not found after authentication. Cannot save session."
            )

    async def _handle_email_2fa(self):
        code = input("Enter Email OTP Code: ")
        try:
            self.auth_api.verify2_fa_email_code(
                two_factor_email_code=TwoFactorEmailCode(code=code)
            )
            logger.info("Email OTP Verified.")
        except ApiException as e:
            logger.error(f"Email OTP verification failed: {e.body}")
            raise

    async def _handle_2fa(self):
        code = input("Enter Authenticator App Code: ")
        try:
            self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code=code))
            logger.info("Authenticator App Code Verified.")
        except ApiException as e:
            logger.error(f"Authenticator App Code verification failed: {e.body}")
            raise
