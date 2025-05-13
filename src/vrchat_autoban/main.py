import os
from typing import List, Tuple

import pendulum
import vrchatapi
from loguru import logger
from tqdm import tqdm
from vrchatapi.api import authentication_api, groups_api

from vrchat_autoban.api.authenticator import VRChatAuthenticator
from vrchat_autoban.api.moderator import VRChatGroupModerator
from vrchat_autoban.api.vrchat_api import VRChatAPI
from vrchat_autoban.config import settings
from vrchat_autoban.data.json_user_loader import JSONUserLoader
from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.data.user_loader import TextUserLoader
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.models.user import User
from vrchat_autoban.utils.file_handler import AsyncFileHandler
from vrchat_autoban.utils.interfaces import FileHandler
from vrchat_autoban.utils.rate_limiter import ProgressBarRateLimiter


def create_vrchat_api(
    processed_user_tracker: ProcessedUserTracker,
    file_handler: FileHandler,
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

    authenticator = VRChatAuthenticator(auth_api, file_handler)
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

    # Save processed users after moderation
    await api.moderator.processed_user_tracker.save()

    end_time = pendulum.now()
    return start_time, end_time


def setup_logging():
    logger.add("vrchat_moderation.log", rotation="1 day")


def log_moderation_results(start_time: pendulum.DateTime, end_time: pendulum.DateTime):
    duration = end_time - start_time
    logger.info(
        f"Moderation process completed at {end_time}. Total duration: {duration}"
    )


async def load_users(file_handler: FileHandler) -> List[User]:
    json_users_file, text_users_file = get_user_file_paths()
    json_user_loader = JSONUserLoader(file_handler, json_users_file)
    text_user_loader = TextUserLoader(file_handler, text_users_file)

    json_users = await json_user_loader.load_users()
    text_users = await text_user_loader.load_users()

    return json_users + text_users


async def setup_processed_user_tracker(
    file_handler: FileHandler,
) -> ProcessedUserTracker:
    processed_users_file = get_processed_users_file_path()
    tracker = ProcessedUserTracker(file_handler, processed_users_file)
    await tracker.load()
    return tracker


async def setup_moderation_environment(
    file_handler: FileHandler,
) -> Tuple[List[User], ProcessedUserTracker]:
    users = await load_users(file_handler)
    processed_user_tracker = await setup_processed_user_tracker(file_handler)

    return users, processed_user_tracker


def get_config_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def get_user_file_paths() -> Tuple[str, str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_users_file = os.path.join(base_dir, "crashers.json")
    text_users_file = os.path.join(base_dir, "crasher_id_dump.txt")
    return json_users_file, text_users_file


def get_processed_users_file_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "processed_users.json"
    )


async def main():
    setup_logging()
    file_handler = AsyncFileHandler()

    users_to_ban, processed_user_tracker = await setup_moderation_environment(
        file_handler
    )
    api = create_vrchat_api(processed_user_tracker, file_handler)
    await api.authenticate()

    start_time, end_time = await run_moderation(api, users_to_ban, settings.group_id)
    log_moderation_results(start_time, end_time)
