from vrchat_autoban.utils.interfaces import FileHandler
from vrchat_autoban.models.user import User


from loguru import logger


import os
from typing import List


class TextUserLoader:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path

    async def load_users(self) -> List[User]:
        try:
            content = await self.file_handler.read_file(self.file_path)
            user_ids = content.strip().split(",")
            return [
                User(id=user_id, name="DCN Dump User")
                for user_id in user_ids
                if user_id
            ]
        except FileNotFoundError:
            logger.error(
                f"User file '{self.file_path}' not found. Current working directory: {os.getcwd()}"
            )
            raise SystemExit(1)
