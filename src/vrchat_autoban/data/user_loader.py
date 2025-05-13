import os  # Keep for CWD logging if needed
from typing import List

from loguru import logger

from vrchat_autoban.models.user import User
from vrchat_autoban.utils.interfaces import FileHandler


class TextUserLoader:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path

    async def load_users(self) -> List[User]:
        try:
            content = await self.file_handler.read_file(self.file_path)
            # Process content to handle potential newlines and ensure clean splitting
            processed_content = content.replace("\n", "").strip()
            if not processed_content:  # Handle empty file
                logger.info(f"Text user file '{self.file_path}' is empty.")
                return []

            user_ids = [
                uid.strip() for uid in processed_content.split(",") if uid.strip()
            ]

            users = [
                User(
                    id=user_id, name="DCN Dump User"
                )  # 'name' is alias for 'display_name'
                for user_id in user_ids
                if user_id  # Ensure user_id is not empty after strip
            ]
            logger.info(f"Loaded {len(users)} users from {self.file_path}")
            return users
        except FileNotFoundError:
            # This case should ideally be handled before calling
            logger.error(
                f"User file '{self.file_path}' not found. Current working directory: {os.getcwd()}"
            )
            return []
