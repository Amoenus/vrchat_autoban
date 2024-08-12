from vrchat_autoban.utils.interfaces import FileHandler


from loguru import logger


import json
from typing import Set


class ProcessedUserTracker:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path
        self.processed_users: Set[str] = set()

    async def load(self):
        try:
            content = await self.file_handler.read_file(self.file_path)
            self.processed_users = set(json.loads(content))
        except FileNotFoundError:
            logger.info(
                f"Processed users file '{self.file_path}' not found. Starting fresh."
            )
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.file_path}'. Please ensure it's valid JSON."
            )
            raise SystemExit(1)

    async def save(self):
        content = json.dumps(list(self.processed_users), indent=2, sort_keys=True)
        await self.file_handler.write_file(self.file_path, content)

    def is_processed(self, user_id: str) -> bool:
        return user_id in self.processed_users

    async def mark_as_processed(self, user_id: str):
        if user_id not in self.processed_users:
            self.processed_users.add(user_id)
            await self.save()  # Save immediately after adding a new user
