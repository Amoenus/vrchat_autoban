from pathlib import Path  # Added
from vrchatapi.api import authentication_api  # type: ignore

from vrchat_autoban.utils.interfaces import FileHandler
from vrchat_autoban.utils.session_manager import SessionManager


class VRChatAuthenticator:
    def __init__(
        self,
        auth_api: authentication_api.AuthenticationApi,
        file_handler: FileHandler,
        session_file_path: Path,  # Added
    ):
        self.session_manager = SessionManager(
            auth_api, file_handler, session_file_path
        )  # Modified

    async def authenticate(self):
        await self.session_manager.authenticate_user()
