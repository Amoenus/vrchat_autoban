import json
from typing import Set

from loguru import logger

from vrchat_autoban.utils.interfaces import FileHandler


class ProcessedUserTracker:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path
        self.processed_users: Set[str] = set()

    async def load(self):
        try:
            content = await self.file_handler.read_file(self.file_path)
            self.processed_users = set(json.loads(content))
            logger.info(
                f"Loaded {len(self.processed_users)} processed users from {self.file_path}"
            )
        except FileNotFoundError:
            logger.info(
                f"Processed users file '{self.file_path}' not found. Starting fresh for this action type."
            )
            self.processed_users = set()  # Ensure it's initialized
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.file_path}'. Please ensure it's valid JSON. Starting fresh for this action type."
            )
            self.processed_users = set()  # Ensure it's initialized
        except Exception as e:
            logger.error(
                f"Unexpected error loading processed users from '{self.file_path}': {e}. Starting fresh."
            )
            self.processed_users = set()

    async def save(self):
        try:
            # Ensure parent directory exists before trying to write
            # This might be better handled at app startup or when file_path is first determined
            # from pathlib import Path
            # Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)

            content = json.dumps(list(self.processed_users), indent=2, sort_keys=True)
            await self.file_handler.write_file(self.file_path, content)
            logger.debug(  # Changed to debug for less verbose regular operation
                f"Saved {len(self.processed_users)} processed users to {self.file_path}"
            )
        except Exception as e:
            logger.error(f"Failed to save processed users to {self.file_path}: {e}")

    def is_processed(self, user_id: str) -> bool:
        is_proc = user_id in self.processed_users
        if is_proc:
            # This log can be quite verbose if many users are already processed.
            # Consider making it DEBUG or only logging from the main loop.
            logger.debug(
                f"User {user_id} found in processed list '{self.file_path}'. Skipping associated action."
            )
        return is_proc

    async def mark_as_processed(self, user_id: str):
        if user_id not in self.processed_users:
            self.processed_users.add(user_id)
            # Save immediately to ensure data integrity on interruption
            await self.save()
        # else:
        # logger.debug(f"User {user_id} was already in the set for {self.file_path}, no new mark needed.")
