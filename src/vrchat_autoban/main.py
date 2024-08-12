import os
from typing import List, Tuple

from loguru import logger
from tqdm import tqdm
import vrchatapi
from vrchatapi.api import authentication_api, groups_api
import pendulum

from vrchat_autoban.api.authenticator import VRChatAuthenticator
from vrchat_autoban.api.moderator import VRChatGroupModerator
from vrchat_autoban.api.vrchat_api import VRChatAPI
from vrchat_autoban.config import Config
from vrchat_autoban.data.json_user_loader import JSONUserLoader
from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.data.user_loader import TextUserLoader
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.models.user import User
from vrchat_autoban.utils.file_handler import AsyncFileHandler
from vrchat_autoban.utils.interfaces import FileHandler
from vrchat_autoban.utils.rate_limiter import ProgressBarRateLimiter


def create_vrchat_api(
    config: Config,
    processed_user_tracker: ProcessedUserTracker,
    file_handler: FileHandler,
) -> VRChatAPI:

    api_client = vrchatapi.ApiClient(
        vrchatapi.Configuration(
            username=config.username,
            password=config.password,
        )
    )
    api_client.user_agent = (
        "VRChatGroupModerationScript/1.0 (https://github.com/Amoenus/vrchat_autoban)"
    )

    auth_api = authentication_api.AuthenticationApi(api_client)
    groups_api_instance = groups_api.GroupsApi(api_client)

    authenticator = VRChatAuthenticator(auth_api, file_handler)
    rate_limiter = ProgressBarRateLimiter(config.rate_limit)
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


async def setup_moderation_environment(
    file_handler: FileHandler,
) -> Tuple[Config, List[User], ProcessedUserTracker]:
    config_file, json_users_file, users_file, processed_users_file = get_file_paths()

    config = await Config.load(file_handler, config_file)
    user_loader = TextUserLoader(file_handler, users_file)
    json_user_loader = JSONUserLoader(file_handler, json_users_file)
    users = await user_loader.load_users() + await json_user_loader.load_users()

    processed_user_tracker = ProcessedUserTracker(file_handler, processed_users_file)
    await processed_user_tracker.load()

    return config, users, processed_user_tracker


def get_file_paths() -> Tuple[str, str, str, str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "config.json")
    json_users_file = os.path.join(script_dir, "crashers.json")
    users_file = os.path.join(script_dir, "crasher_id_dump.txt")
    processed_users_file = os.path.join(script_dir, "processed_users.json")
    return config_file, json_users_file, users_file, processed_users_file


async def main():
    setup_logging()
    file_handler = AsyncFileHandler()

    config, users_to_ban, processed_user_tracker = await setup_moderation_environment(
        file_handler
    )
    api = create_vrchat_api(config, processed_user_tracker, file_handler)
    await api.authenticate()

    start_time, end_time = await run_moderation(api, users_to_ban, config.group_id)
    log_moderation_results(start_time, end_time)
