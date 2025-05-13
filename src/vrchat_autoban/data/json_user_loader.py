import json
import os
from typing import List

from loguru import logger

from vrchat_autoban.models.user import User
from vrchat_autoban.utils.interfaces import FileHandler


class JSONUserLoader:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path

    async def load_users(self) -> List[User]:
        try:
            content = await self.file_handler.read_file(self.file_path)
            data = json.loads(content)
        except FileNotFoundError:
            logger.error(f"User file '{self.file_path}' not found.")
            logger.error(f"Current working directory: {os.getcwd()}")
            logger.error("Please ensure the user file exists in the correct location.")
            raise SystemExit(1)
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.file_path}'. Please ensure it's valid JSON."
            )
            raise SystemExit(1)

        users = []
        for member in data:
            user_data = member.get("user", {})
            user_id = user_data.get("id")
            display_name = user_data.get("displayName")
            if user_id and display_name:
                user = User(id=user_id, name=display_name)
                users.append(user)
            else:
                logger.warning(f"Skipping user with incomplete data: {user_data}")

        logger.info(f"Loaded {len(users)} users from {self.file_path}")
        return users
