import os
import json
from typing import List, Protocol, Tuple, Set
from enum import Enum, auto

import vrchatapi
from vrchatapi.api import authentication_api, groups_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.models.ban_group_member_request import BanGroupMemberRequest
from vrchatapi.exceptions import ApiException
from loguru import logger
import pendulum
from tqdm import tqdm
from pydantic import BaseModel, Field
import asyncio
import aiofiles


class BanStatus(Enum):
    NEWLY_BANNED = auto()
    ALREADY_BANNED = auto()
    ALREADY_PROCESSED = auto()
    FAILED = auto()


class FileHandler(Protocol):
    async def read_file(self, file_path: str) -> str: ...
    async def write_file(self, file_path: str, content: str): ...


class AsyncFileHandler:
    async def read_file(self, file_path: str) -> str:
        async with aiofiles.open(file_path, "r") as file:
            return await file.read()

    async def write_file(self, file_path: str, content: str):
        async with aiofiles.open(file_path, "w") as file:
            await file.write(content)


class User(BaseModel):
    id: str
    displayName: str = Field(alias="display_name")


class Config(BaseModel):
    username: str
    password: str
    group_id: str
    rate_limit: int = Field(default=60)

    @classmethod
    async def load(cls, file_handler: FileHandler, file_path: str) -> "Config":
        try:
            content = await file_handler.read_file(file_path)
            data = json.loads(content)
            return cls(**data)
        except FileNotFoundError:
            logger.error(
                f"Config file '{file_path}' not found. Current working directory: {os.getcwd()}"
            )
            raise SystemExit(1)
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{file_path}'. Please ensure it's valid JSON."
            )
            raise SystemExit(1)


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


class TextUserLoader:
    def __init__(self, file_handler: FileHandler, file_path: str):
        self.file_handler = file_handler
        self.file_path = file_path

    async def load_users(self) -> List[User]:
        try:
            content = await self.file_handler.read_file(self.file_path)
            user_ids = content.strip().split(",")
            return [
                User(id=user_id, display_name="DCN Dump User")
                for user_id in user_ids
                if user_id
            ]
        except FileNotFoundError:
            logger.error(
                f"User file '{self.file_path}' not found. Current working directory: {os.getcwd()}"
            )
            raise SystemExit(1)


class RateLimiter(Protocol):
    async def wait(self): ...


class ProgressBarRateLimiter:
    def __init__(self, limit: int):
        self.limit = limit

    async def wait(self):
        with tqdm(total=self.limit, desc="Rate limit", unit="s", leave=False) as pbar:
            for _ in range(self.limit):
                await asyncio.sleep(1)
                pbar.update(1)


class VRChatAuthenticator:
    def __init__(self, auth_api: authentication_api.AuthenticationApi):
        self.auth_api = auth_api

    def authenticate(self):
        try:
            current_user = self.auth_api.get_current_user()
            logger.info(f"Logged in as: {current_user.display_name}")
        except UnauthorizedException as e:
            if e.status == 200:
                if "Email 2 Factor Authentication" in str(e):
                    self._handle_email_2fa()
                elif "2 Factor Authentication" in str(e):
                    self._handle_2fa()
                current_user = self.auth_api.get_current_user()
            else:
                raise
        except vrchatapi.ApiException as e:
            logger.error(f"Exception when calling API: {e}")
            raise

    def _handle_email_2fa(self):
        code = input("Email 2FA Code: ")
        self.auth_api.verify2_fa_email_code(
            two_factor_email_code=TwoFactorEmailCode(code)
        )

    def _handle_2fa(self):
        code = input("2FA Code: ")
        self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code))


class VRChatGroupModerator:
    def __init__(
        self,
        groups_api: groups_api.GroupsApi,
        rate_limiter: RateLimiter,
        processed_user_tracker: ProcessedUserTracker,
    ):
        self.groups_api = groups_api
        self.rate_limiter = rate_limiter
        self.processed_user_tracker = processed_user_tracker

    async def ban_user(self, group_id: str, user_id: str) -> BanStatus:
        if self.processed_user_tracker.is_processed(user_id):
            logger.info(f"User {user_id} already processed. Skipping.")
            return BanStatus.ALREADY_PROCESSED

        try:
            ban_request = BanGroupMemberRequest(user_id=user_id)
            result = self.groups_api.ban_group_member(
                group_id, ban_group_member_request=ban_request
            )
            logger.info(f"Ban result: {result}")
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self.rate_limiter.wait()
            return BanStatus.NEWLY_BANNED
        except ApiException as e:
            if e.status == 400:
                try:
                    error_body = json.loads(e.body)
                    if "User is already banned" in error_body.get("error", {}).get(
                        "message", ""
                    ):
                        logger.info(
                            f"User {user_id} is already banned. Marking as processed."
                        )
                        await self.processed_user_tracker.mark_as_processed(user_id)
                        await self.rate_limiter.wait()
                        return BanStatus.ALREADY_BANNED
                except json.JSONDecodeError:
                    pass  # If we can't parse the JSON, we'll fall through to the general error handling
            logger.error(
                f"Exception when calling GroupsApi->ban_group_member: ({e.status}) {e.reason}"
            )
            logger.error(f"Response body: {e.body}")
            await self.rate_limiter.wait()  # Wait for rate limit after failed API call
            return BanStatus.FAILED


class VRChatAPI:
    def __init__(
        self, authenticator: VRChatAuthenticator, moderator: VRChatGroupModerator
    ):
        self.authenticator = authenticator
        self.moderator = moderator

    def authenticate(self):
        self.authenticator.authenticate()

    async def ban_user_from_group(self, group_id: str, user_id: str) -> BanStatus:
        return await self.moderator.ban_user(group_id, user_id)


def get_file_paths() -> Tuple[str, str, str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "config.json")
    users_file = os.path.join(script_dir, "crasher_id_dump.txt")
    processed_users_file = os.path.join(script_dir, "processed_users.json")
    return config_file, users_file, processed_users_file


async def setup_moderation_environment(
    file_handler: FileHandler,
) -> Tuple[Config, List[User], ProcessedUserTracker]:
    config_file, users_file, processed_users_file = get_file_paths()

    config = await Config.load(file_handler, config_file)

    user_loader = TextUserLoader(file_handler, users_file)
    users = await user_loader.load_users()

    processed_user_tracker = ProcessedUserTracker(file_handler, processed_users_file)
    await processed_user_tracker.load()

    return config, users, processed_user_tracker


def create_vrchat_api(
    config: Config, processed_user_tracker: ProcessedUserTracker
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

    authenticator = VRChatAuthenticator(auth_api)
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
            logger.info(f"Successfully banned user {user.displayName} (ID: {user.id})")
        elif ban_status == BanStatus.ALREADY_BANNED:
            logger.info(f"User {user.displayName} (ID: {user.id}) was already banned")
        elif ban_status == BanStatus.ALREADY_PROCESSED:
            logger.info(f"User {user.displayName} (ID: {user.id}) was already processed")
        elif ban_status == BanStatus.FAILED:
            logger.warning(f"Failed to ban user {user.displayName} (ID: {user.id})")
        else:
            logger.error(f"Unknown ban status for user {user.displayName} (ID: {user.id})")

    # Save processed users after moderation
    await api.moderator.processed_user_tracker.save()

    end_time = pendulum.now()
    return start_time, end_time


def log_moderation_results(start_time: pendulum.DateTime, end_time: pendulum.DateTime):
    duration = end_time - start_time
    logger.info(
        f"Moderation process completed at {end_time}. Total duration: {duration}"
    )


def setup_logging():
    logger.add("vrchat_moderation.log", rotation="1 day")


async def main():
    setup_logging()
    file_handler = AsyncFileHandler()

    config, users_to_ban, processed_user_tracker = await setup_moderation_environment(
        file_handler
    )
    api = create_vrchat_api(config, processed_user_tracker)
    api.authenticate()

    start_time, end_time = await run_moderation(api, users_to_ban, config.group_id)
    log_moderation_results(start_time, end_time)


if __name__ == "__main__":
    asyncio.run(main())
