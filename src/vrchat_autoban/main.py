import argparse
import asyncio
import os
from pathlib import Path
from typing import List, Tuple, Optional

import pendulum
import platformdirs
import vrchatapi
from loguru import logger
from tqdm import tqdm
from vrchatapi.api import authentication_api, groups_api, playermoderation_api

from vrchat_autoban.api.authenticator import VRChatAuthenticator
from vrchat_autoban.api.moderator import VRChatGroupModerator
from vrchat_autoban.api.user_moderator import VRChatUserModerator
from vrchat_autoban.api.vrchat_api import VRChatAPI
from vrchat_autoban.config import settings
from vrchat_autoban.constants import (
    APP_AUTHOR,
    APP_NAME,
    DEFAULT_CRASHER_ID_DUMP_FILENAME,
    DEFAULT_CRASHERS_JSON_FILENAME,
    DEFAULT_LOG_FILENAME,
    DEFAULT_PROCESSED_ACCOUNT_BLOCKS_FILENAME,
    DEFAULT_PROCESSED_GROUP_BANS_FILENAME,
    DEFAULT_SESSION_FILENAME,
)
from vrchat_autoban.data.json_user_loader import JSONUserLoader
from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.data.user_loader import TextUserLoader
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.models.user import User
from vrchat_autoban.models.user_block_status import UserBlockStatus
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
    parser = argparse.ArgumentParser(
        description="VRChat Group Auto-Ban & User Block Tool."
    )
    # Base directory for source files, to default to user's provided structure
    source_base_dir = Path(os.path.dirname(os.path.abspath(__file__)))

    # User-provided input files
    parser.add_argument(
        "--crashers-file",
        type=Path,
        default=source_base_dir / DEFAULT_CRASHERS_JSON_FILENAME,
        help=f"Path to JSON user data (VRCX export). (Default: .../{DEFAULT_CRASHERS_JSON_FILENAME})",
    )
    parser.add_argument(
        "--crasher-id-dump-file",
        type=Path,
        default=source_base_dir / DEFAULT_CRASHER_ID_DUMP_FILENAME,
        help=f"Path to text file with comma-separated user IDs. (Default: .../{DEFAULT_CRASHER_ID_DUMP_FILENAME})",
    )

    parser.add_argument(
        "--processed-group-bans-file",
        type=Path,
        default=source_base_dir / DEFAULT_PROCESSED_GROUP_BANS_FILENAME,
        help=f"JSON file for tracking processed group bans. (Default: .../{DEFAULT_PROCESSED_GROUP_BANS_FILENAME})",
    )
    parser.add_argument(
        "--processed-account-blocks-file",
        type=Path,
        default=source_base_dir / DEFAULT_PROCESSED_ACCOUNT_BLOCKS_FILENAME,
        help=f"JSON file for tracking processed account blocks. (Default: .../{DEFAULT_PROCESSED_ACCOUNT_BLOCKS_FILENAME})",
    )

    parser.add_argument(
        "--session-file",
        type=Path,
        default=source_base_dir / DEFAULT_SESSION_FILENAME,
        help=f"Path to VRChat session JSON. (Default: .../{DEFAULT_SESSION_FILENAME})",
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
    group_ban_tracker: Optional[ProcessedUserTracker],
    account_block_tracker: Optional[ProcessedUserTracker],
    file_handler: FileHandler,
    session_file_path: Path,
) -> VRChatAPI:
    api_client = vrchatapi.ApiClient(
        vrchatapi.Configuration(username=settings.username, password=settings.password)
    )
    api_client.user_agent = (
        "VRChatModerationTool/1.1 (https://github.com/Amoenus/vrchat_autoban)"
    )

    auth_api = authentication_api.AuthenticationApi(api_client)
    authenticator = VRChatAuthenticator(auth_api, file_handler, session_file_path)
    rate_limiter = ProgressBarRateLimiter(settings.rate_limit)

    group_moderator = None
    if (
        settings.get("group_id") and group_ban_tracker
    ):  # Only create if group_id is set and tracker exists
        groups_api_instance = groups_api.GroupsApi(api_client)
        group_moderator = VRChatGroupModerator(
            groups_api_instance, rate_limiter, group_ban_tracker
        )

    user_moderator = None
    if (
        settings.get("user_side_blocking_enabled") and account_block_tracker
    ):  # Only create if enabled and tracker exists
        playmod_api_instance = playermoderation_api.PlayermoderationApi(api_client)
        user_moderator = VRChatUserModerator(
            playmod_api_instance, rate_limiter, account_block_tracker
        )

    if not group_moderator and not user_moderator:
        # This case should be caught earlier by config validation, but as a safeguard:
        raise ValueError(
            "Neither group moderation nor user blocking is configured or enabled properly."
        )

    return VRChatAPI(authenticator, group_moderator, user_moderator)


async def run_moderation(
    api: VRChatAPI, users: List[User]
) -> Tuple[pendulum.DateTime, pendulum.DateTime]:
    start_time = pendulum.now()
    logger.info(f"Starting moderation process at {start_time}")

    if not users:
        logger.warning("No users loaded to moderate. Exiting moderation early.")
        return start_time, pendulum.now()

    total_users = len(users)
    processed_count = 0

    for user_obj in tqdm(users, desc="Moderating users", unit="user"):
        processed_count += 1
        current_user_log_name = f"{user_obj.display_name} (ID: {user_obj.id})"
        logger.info(
            f"Processing user {processed_count}/{total_users}: {current_user_log_name}"
        )

        # Group Ban Logic
        if settings.get("group_id") and api.group_moderator:
            ban_status, actual_display_name = await api.ban_user_from_group(
                settings.group_id, user_obj.id
            )
            log_name_for_ban = (
                actual_display_name if actual_display_name else user_obj.display_name
            )

            if ban_status == BanStatus.NEWLY_BANNED:
                logger.info(
                    f"Successfully group-banned user {log_name_for_ban} (ID: {user_obj.id})"
                )
            elif ban_status == BanStatus.ALREADY_BANNED:
                logger.info(
                    f"User {log_name_for_ban} (ID: {user_obj.id}) was already group-banned (per API)."
                )
            elif (
                ban_status == BanStatus.ALREADY_PROCESSED
            ):  # This means processed by script for group ban
                logger.info(
                    f"User {log_name_for_ban} (ID: {user_obj.id}) was already processed for group ban by this script."
                )
            elif ban_status == BanStatus.FAILED:
                logger.warning(
                    f"Failed to group-ban user {log_name_for_ban} (ID: {user_obj.id})"
                )
            else:
                logger.error(
                    f"Unknown group ban status for user {log_name_for_ban} (ID: {user_obj.id})"
                )
        elif settings.get("group_id") and not api.group_moderator:
            logger.warning(
                "Group ID is configured, but group moderator was not initialized. Skipping group bans."
            )

        # User-Side Blocking Logic
        if settings.get("user_side_blocking_enabled") and api.user_moderator:
            block_status = await api.block_user_on_account(user_obj.id)
            if (
                block_status == UserBlockStatus.BLOCK_SUCCESSFUL
            ):  # Changed from NEWLY_BLOCKED
                logger.info(
                    f"Successfully ensured user {current_user_log_name} is account-blocked."
                )
            # ALREADY_BLOCKED (by API pre-check) is removed as pre-check is removed.
            elif (
                block_status == UserBlockStatus.ALREADY_PROCESSED_BY_SCRIPT
            ):  # Changed from ALREADY_PROCESSED
                logger.info(
                    f"User {current_user_log_name} was already processed for account-blocking by this script."
                )
            elif block_status == UserBlockStatus.FAILED_TO_BLOCK:
                logger.warning(f"Failed to account-block user {current_user_log_name}")
            # SKIPPED_API_ERROR is removed as pre-check is removed.
            else:
                logger.error(
                    f"Unknown account-block status for user {current_user_log_name}"
                )
        elif settings.get("user_side_blocking_enabled") and not api.user_moderator:
            logger.warning(
                "User-side blocking is enabled, but user moderator was not initialized. Skipping account blocks."
            )

    # Save processed user lists
    if api.group_moderator and api.group_moderator.processed_user_tracker:
        logger.info("Attempting to save processed users list for group bans...")
        await api.group_moderator.processed_user_tracker.save()
    if api.user_moderator and api.user_moderator.processed_user_tracker:
        logger.info("Attempting to save processed users list for account blocks...")
        await api.user_moderator.processed_user_tracker.save()

    end_time = pendulum.now()
    return start_time, end_time


def setup_logging(log_file_path: Path):
    ensure_directory_exists(log_file_path)
    logger.remove()
    # Console output through tqdm for cleaner progress bars
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True, level="INFO")
    # File logging
    logger.add(
        log_file_path, rotation="1 day", level="DEBUG", enqueue=True
    )  # Log DEBUG to file
    logger.info(f"Logging to console (INFO) and file ({log_file_path}) (DEBUG)")


def log_moderation_results(start_time: pendulum.DateTime, end_time: pendulum.DateTime):
    duration = end_time - start_time
    logger.info(
        f"Moderation process completed at {end_time}. Total duration: {duration.in_words(locale='en')}."
    )


async def load_users(
    file_handler: FileHandler, json_users_file: Path, text_users_file: Path
) -> List[User]:
    json_user_loader = JSONUserLoader(file_handler, str(json_users_file))
    text_user_loader = TextUserLoader(file_handler, str(text_users_file))
    loaded_users: List[User] = []

    if json_users_file.exists() and json_users_file.is_file():
        try:
            loaded_users.extend(await json_user_loader.load_users())
        except Exception as e:
            logger.error(
                f"Failed to load users from JSON file {json_users_file.resolve()}: {e}"
            )
    elif json_users_file.exists() and not json_users_file.is_file():
        logger.error(
            f"Expected JSON user file at {json_users_file.resolve()} is a directory, not a file. Skipping."
        )
    else:
        logger.warning(
            f"JSON user file not found: {json_users_file.resolve()}. Skipping."
        )

    if text_users_file.exists() and text_users_file.is_file():
        try:
            loaded_users.extend(await text_user_loader.load_users())
        except Exception as e:
            logger.error(
                f"Failed to load users from text file {text_users_file.resolve()}: {e}"
            )
    elif text_users_file.exists() and not text_users_file.is_file():
        logger.error(
            f"Expected text user file at {text_users_file.resolve()} is a directory, not a file. Skipping."
        )
    else:
        logger.warning(
            f"Text user file not found: {text_users_file.resolve()}. Skipping."
        )

    if not loaded_users:
        logger.warning("No user IDs were loaded from any source file.")
        return []

    # Deduplicate users based on ID, preferring entries that might have more info
    unique_users_dict = {user.id: user for user in loaded_users}
    unique_users_list = list(unique_users_dict.values())
    if len(unique_users_list) < len(loaded_users):
        logger.info(
            f"Deduplicated user list from {len(loaded_users)} to {len(unique_users_list)} users based on unique IDs."
        )
    else:
        logger.info(f"Loaded {len(unique_users_list)} unique users.")

    return unique_users_list


async def setup_tracker(
    file_handler: FileHandler, tracker_file_path: Path
) -> ProcessedUserTracker:
    ensure_directory_exists(tracker_file_path)
    tracker = ProcessedUserTracker(file_handler, str(tracker_file_path))
    await tracker.load()
    return tracker


async def main_async():
    args = parse_arguments()
    setup_logging(args.log_file)

    if (
        not settings.get("username")
        or settings.username in ["changeme", "your_vrchat_username"]
        or not settings.get("password")
        or settings.password in ["changemeaswell", "your_vrchat_password"]
    ):
        logger.error(
            "Username or password not configured correctly. Please set them in .secrets.toml or environment variables."
        )
        return

    perform_group_bans = bool(settings.get("group_id"))
    perform_account_blocks = settings.get("user_side_blocking_enabled", False)

    if not perform_group_bans and not perform_account_blocks:
        logger.error(
            "No action configured. 'group_id' must be set for group bans, and/or 'user_side_blocking_enabled' must be true for account blocks."
        )
        return

    file_handler = AsyncFileHandler()
    group_ban_tracker: Optional[ProcessedUserTracker] = None
    account_block_tracker: Optional[ProcessedUserTracker] = None

    try:
        # Setup trackers based on configuration
        if perform_group_bans:
            ensure_directory_exists(args.processed_group_bans_file)
            group_ban_tracker = await setup_tracker(
                file_handler, args.processed_group_bans_file
            )
        if perform_account_blocks:
            ensure_directory_exists(args.processed_account_blocks_file)
            account_block_tracker = await setup_tracker(
                file_handler, args.processed_account_blocks_file
            )

        ensure_directory_exists(args.session_file)  # For session manager

        users_to_moderate = await load_users(
            file_handler, args.crashers_file, args.crasher_id_dump_file
        )

        if not users_to_moderate:
            logger.info("No users to process. Exiting.")
            return

        api = create_vrchat_api(
            group_ban_tracker, account_block_tracker, file_handler, args.session_file
        )

        logger.info("Attempting to authenticate with VRChat...")
        await api.authenticate()

        start_time, end_time = await run_moderation(api, users_to_moderate)
        log_moderation_results(start_time, end_time)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.warning("Moderation process interrupted.")
        if group_ban_tracker:
            logger.info("Attempting to save group ban tracker due to interruption...")
            await group_ban_tracker.save()
        if account_block_tracker:
            logger.info(
                "Attempting to save account block tracker due to interruption..."
            )
            await account_block_tracker.save()
    except Exception as e:
        logger.critical(
            f"An unhandled error occurred in main_async: {e}", exc_info=True
        )
    finally:
        logger.info("VRChat Moderation Tool execution finished or was terminated.")
