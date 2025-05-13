import json
import os  # Keep for CWD logging if needed, though error now raised from main
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
            # This case should ideally be handled before calling,
            # but as a safeguard if called directly:
            logger.error(f"User file '{self.file_path}' not found.")
            logger.error(
                f"Current working directory: {os.getcwd()}"
            )  # For context if error occurs here
            return []  # Return empty list, main.py will log appropriate warning
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.file_path}'. Please ensure it's valid JSON."
            )
            # Consider raising a custom exception or returning empty to be handled by caller
            raise SystemExit(f"Invalid JSON in {self.file_path}")

        users = []
        for member in data:
            user_data = member.get("user", {})
            user_id = user_data.get("id")
            display_name = user_data.get(
                "displayName"
            )  # Pydantic model User uses alias 'name' for this
            if user_id and display_name:
                user = User(
                    id=user_id, name=display_name
                )  # 'name' is the alias for 'display_name' field
                users.append(user)
            else:
                logger.warning(
                    f"Skipping user with incomplete data in {self.file_path}: {user_data}"
                )

        logger.info(f"Loaded {len(users)} users from {self.file_path}")
        return users
