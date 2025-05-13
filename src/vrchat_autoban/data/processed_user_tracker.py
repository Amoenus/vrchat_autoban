import json
from typing import Set

from loguru import logger

from vrchat_autoban.utils.interfaces import FileHandler


class ProcessedUserTracker:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path
        self.processed_users: Set[str] = set()
        # Suggestion from review: Saving on every addition is safer.
        # For very large numbers of new users, an alternative might be to save
        # periodically or at the end of the run_moderation loop.
        # Current approach is kept for data integrity.

    async def load(self):
        try:
            content = await self.file_handler.read_file(self.file_path)
            self.processed_users = set(json.loads(content))
            logger.info(
                f"Loaded {len(self.processed_users)} processed users from {self.file_path}"
            )
        except FileNotFoundError:
            logger.info(
                f"Processed users file '{self.file_path}' not found. Starting fresh."
            )
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.file_path}'. Please ensure it's valid JSON. Starting fresh."
            )
            # Optionally, could raise SystemExit or try to backup/rename the corrupted file.
            # For now, starting fresh is a simple recovery.
            self.processed_users = set()

    async def save(self):
        try:
            content = json.dumps(list(self.processed_users), indent=2, sort_keys=True)
            await self.file_handler.write_file(self.file_path, content)
            logger.debug(
                f"Saved {len(self.processed_users)} processed users to {self.file_path}"
            )
        except Exception as e:
            logger.error(f"Failed to save processed users to {self.file_path}: {e}")

    def is_processed(self, user_id: str) -> bool:
        is_proc = user_id in self.processed_users
        if is_proc:
            logger.info(f"User {user_id} already processed. Skipping.")
        return is_proc

    async def mark_as_processed(self, user_id: str):
        if user_id not in self.processed_users:
            self.processed_users.add(user_id)
            # The review noted saving immediately is safer, which is current behavior.
            # If performance becomes an issue for extremely large lists,
            # this save could be deferred or batched.
            await self.save()
