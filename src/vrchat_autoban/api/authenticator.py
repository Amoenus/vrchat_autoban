from pathlib import Path

from vrchatapi.api import authentication_api

from vrchat_autoban.utils.interfaces import FileHandler
from vrchat_autoban.utils.session_manager import SessionManager


class VRChatAuthenticator:
    def __init__(
        self,
        auth_api: authentication_api.AuthenticationApi,
        file_handler: FileHandler,
        session_file_path: Path,
    ):
        self.session_manager = SessionManager(auth_api, file_handler, session_file_path)

    async def authenticate(self):
        await self.session_manager.authenticate_user()
