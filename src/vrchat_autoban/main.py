# src/vrchat_autoban/main.py
import argparse
import os
from pathlib import Path
from typing import List, Tuple

import pendulum
import platformdirs
import vrchatapi
from loguru import logger
from tqdm import tqdm
from vrchatapi.api import authentication_api, groups_api

from vrchat_autoban.api.authenticator import VRChatAuthenticator
from vrchat_autoban.api.moderator import VRChatGroupModerator
from vrchat_autoban.api.vrchat_api import VRChatAPI
from vrchat_autoban.config import settings
from vrchat_autoban.constants import (
    APP_NAME,
    APP_AUTHOR,
    DEFAULT_CRASHERS_JSON_FILENAME,
    DEFAULT_CRASHER_ID_DUMP_FILENAME,
    DEFAULT_PROCESSED_USERS_FILENAME,
    DEFAULT_SESSION_FILENAME,
    DEFAULT_LOG_FILENAME,
)
from vrchat_autoban.data.json_user_loader import JSONUserLoader
from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.data.user_loader import TextUserLoader
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.models.user import User
from vrchat_autoban.utils.file_handler import AsyncFileHandler
from vrchat_autoban.utils.interfaces import FileHandler
from vrchat_autoban.utils.rate_limiter import ProgressBarRateLimiter


def ensure_directory_exists(file_path: Path):
    """Ensures the directory for the given file_path exists."""
    parent_dir = file_path.parent
    if not parent_dir.exists():
        parent_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {parent_dir}")


def parse_arguments():
    parser = argparse.ArgumentParser(description="VRChat Group Auto-Ban Tool.")

    # Base directory for source files, to default to user's provided structure
    source_base_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    # User-provided input files
    parser.add_argument(
        "--crashers-file",
        type=Path,
        default=source_base_dir / DEFAULT_CRASHERS_JSON_FILENAME,
        help=f"Path to the JSON file containing user data from VRCX group export. (Default: {source_base_dir / DEFAULT_CRASHERS_JSON_FILENAME})",
    )
    parser.add_argument(
        "--crasher-id-dump-file",
        type=Path,
        default=source_base_dir / DEFAULT_CRASHER_ID_DUMP_FILENAME,
        help=f"Path to the text file containing comma-separated user IDs. (Default: {source_base_dir / DEFAULT_CRASHER_ID_DUMP_FILENAME})",
    )

    # Application-managed files - defaulting to source directory for reuse
    parser.add_argument(
        "--processed-users-file",
        type=Path,
        default=source_base_dir / DEFAULT_PROCESSED_USERS_FILENAME,  # Changed default
        help=f"Path to the JSON file for tracking processed user IDs. (Default: {source_base_dir / DEFAULT_PROCESSED_USERS_FILENAME})",
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        default=source_base_dir / DEFAULT_SESSION_FILENAME,  # Changed default
        help=f"Path to the JSON file for storing VRChat session data. (Default: {source_base_dir / DEFAULT_SESSION_FILENAME})",
    )

    # Log file - still defaults to platformdirs location for good practice
    default_user_log_dir = Path(platformdirs.user_log_dir(APP_NAME, APP_AUTHOR))
    parser.add_argument(
        "--log-file",
        type=Path,
        default=default_user_log_dir / DEFAULT_LOG_FILENAME,
        help=f"Path to the log file. (Default: {default_user_log_dir / DEFAULT_LOG_FILENAME})",
    )
    return parser.parse_args()


def create_vrchat_api(
    processed_user_tracker: ProcessedUserTracker,
    file_handler: FileHandler,
    session_file_path: Path,
) -> VRChatAPI:
    api_client = vrchatapi.ApiClient(
        vrchatapi.Configuration(
            username=settings.username,
            password=settings.password,
        )
    )
    api_client.user_agent = (
        "VRChatGroupModerationScript/1.0 (https://github.com/Amoenus/vrchat_autoban)"
    )

    auth_api = authentication_api.AuthenticationApi(api_client)
    groups_api_instance = groups_api.GroupsApi(api_client)

    authenticator = VRChatAuthenticator(auth_api, file_handler, session_file_path)
    rate_limiter = ProgressBarRateLimiter(settings.rate_limit)
    moderator = VRChatGroupModerator(
        groups_api_instance, rate_limiter, processed_user_tracker
    )

    return VRChatAPI(authenticator, moderator)


async def run_moderation(
    api: VRChatAPI, users: List[User], group_id: str
) -> Tuple[pendulum.DateTime, pendulum.DateTime]:
    start_time = pendulum.now()
    logger.info(f"Starting moderation process at {start_time}")

    if not users:
        logger.warning("No users loaded to moderate. Exiting moderation early.")
        return start_time, pendulum.now()

    for user in tqdm(users, desc="Moderating users", unit="user"):
        ban_status = await api.ban_user_from_group(group_id, user.id)

        if ban_status == BanStatus.NEWLY_BANNED:
            logger.info(f"Successfully banned user {user.display_name} (ID: {user.id})")
        elif ban_status == BanStatus.ALREADY_BANNED:
            logger.info(f"User {user.display_name} (ID: {user.id}) was already banned")
        elif ban_status == BanStatus.ALREADY_PROCESSED:
            logger.info(
                f"User {user.display_name} (ID: {user.id}) was already processed"
            )
        elif ban_status == BanStatus.FAILED:
            logger.warning(f"Failed to ban user {user.display_name} (ID: {user.id})")
        else:
            logger.error(
                f"Unknown ban status for user {user.display_name} (ID: {user.id})"
            )

    await api.moderator.processed_user_tracker.save()

    end_time = pendulum.now()
    return start_time, end_time


def setup_logging(log_file_path: Path):
    ensure_directory_exists(log_file_path)
    logger.remove()
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True, level="INFO")
    logger.add(log_file_path, rotation="1 day", level="INFO")


def log_moderation_results(start_time: pendulum.DateTime, end_time: pendulum.DateTime):
    duration = end_time - start_time
    logger.info(
        f"Moderation process completed at {end_time}. Total duration: {duration.in_words()}"
    )


async def load_users(
    file_handler: FileHandler, json_users_file: Path, text_users_file: Path
) -> List[User]:
    json_user_loader = JSONUserLoader(file_handler, str(json_users_file))
    text_user_loader = TextUserLoader(file_handler, str(text_users_file))

    loaded_json_users = []
    if json_users_file.exists():
        loaded_json_users = await json_user_loader.load_users()
    else:
        logger.warning(f"JSON user file not found: {json_users_file}. Skipping.")

    loaded_text_users = []
    if text_users_file.exists():
        loaded_text_users = await text_user_loader.load_users()
    else:
        logger.warning(f"Text user file not found: {text_users_file}. Skipping.")

    return loaded_json_users + loaded_text_users


async def setup_processed_user_tracker(
    file_handler: FileHandler, processed_users_file: Path
) -> ProcessedUserTracker:
    ensure_directory_exists(processed_users_file)
    tracker = ProcessedUserTracker(file_handler, str(processed_users_file))
    await tracker.load()
    return tracker


async def setup_moderation_environment(
    file_handler: FileHandler,
    json_users_file: Path,
    text_users_file: Path,
    processed_users_file: Path,
) -> Tuple[List[User], ProcessedUserTracker]:
    users = await load_users(file_handler, json_users_file, text_users_file)
    processed_user_tracker = await setup_processed_user_tracker(
        file_handler, processed_users_file
    )

    return users, processed_user_tracker


async def main_async():
    args = parse_arguments()

    setup_logging(args.log_file)
    file_handler = AsyncFileHandler()

    ensure_directory_exists(args.processed_users_file)
    ensure_directory_exists(args.session_file)

    users_to_ban, processed_user_tracker = await setup_moderation_environment(
        file_handler,
        args.crashers_file,
        args.crasher_id_dump_file,
        args.processed_users_file,
    )
    api = create_vrchat_api(processed_user_tracker, file_handler, args.session_file)

    try:
        await api.authenticate()
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        logger.error(
            "Please check your credentials in .secrets.toml (or environment variables) and ensure VRChat services are reachable."
        )
        return

    start_time, end_time = await run_moderation(api, users_to_ban, settings.group_id)
    log_moderation_results(start_time, end_time)
