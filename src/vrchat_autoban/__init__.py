import os
import json
from typing import List, Protocol, Tuple
import vrchatapi
from vrchatapi.api import authentication_api, groups_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.models.ban_group_member_request import BanGroupMemberRequest
from loguru import logger
import pendulum
from tqdm import tqdm
from pydantic import BaseModel, Field
import asyncio
import aiofiles


class User(BaseModel):
    id: str
    displayName: str = Field(alias="display_name")


class UserLoader(Protocol):
    async def load_users(self) -> List[User]: ...


class FileReader(Protocol):
    async def read_file(self, file_path: str) -> str: ...


class AsyncFileReader:
    async def read_file(self, file_path: str) -> str:
        async with aiofiles.open(file_path, "r") as file:
            return await file.read()


class JSONUserLoader:
    def __init__(self, file_reader: FileReader, file_path: str):
        self.file_reader = file_reader
        self.file_path = file_path

    async def load_users(self) -> List[User]:
        try:
            content = await self.file_reader.read_file(self.file_path)
            data = json.loads(content)
            return [User(**member["user"]) for member in data if "user" in member]
        except FileNotFoundError:
            logger.error(
                f"User file '{self.file_path}' not found. Current working directory: {os.getcwd()}"
            )
            raise SystemExit(1)
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{self.file_path}'. Please ensure it's valid JSON."
            )
            raise SystemExit(1)


class TextUserLoader(UserLoader):
    def __init__(self, file_reader: FileReader, file_path: str):
        self.file_reader = file_reader
        self.file_path = file_path

    async def load_users(self) -> List[User]:
        try:
            content = await self.file_reader.read_file(self.file_path)
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


class GroupModerator(Protocol):
    async def ban_user(self, group_id: str, user_id: str) -> bool: ...


class VRChatGroupModerator:
    def __init__(self, groups_api: groups_api.GroupsApi, rate_limiter: RateLimiter):
        self.groups_api = groups_api
        self.rate_limiter = rate_limiter

    async def ban_user(self, group_id: str, user_id: str) -> bool:
        try:
            ban_request = BanGroupMemberRequest(user_id=user_id)
            result = self.groups_api.ban_group_member(
                group_id, ban_group_member_request=ban_request
            )
            logger.info(f"Ban result: {result}")
            await self.rate_limiter.wait()
            return True
        except vrchatapi.ApiException as e:
            logger.error(f"Exception when calling GroupsApi->ban_group_member: {e}")
            return False


class VRChatAPI:
    def __init__(self, authenticator: VRChatAuthenticator, moderator: GroupModerator):
        self.authenticator = authenticator
        self.moderator = moderator

    def authenticate(self):
        self.authenticator.authenticate()

    async def ban_user_from_group(self, group_id: str, user_id: str) -> bool:
        return await self.moderator.ban_user(group_id, user_id)


class Config(BaseModel):
    username: str
    password: str
    group_id: str
    rate_limit: int = Field(default=60)

    @classmethod
    async def load_config(cls, file_reader: FileReader, file_path: str) -> "Config":
        try:
            content = await file_reader.read_file(file_path)
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


async def moderate_users(api: VRChatAPI, users: List[User], group_id: str):
    for user in tqdm(users, desc="Moderating users", unit="user"):
        if await api.ban_user_from_group(group_id, user.id):
            logger.info(f"Successfully banned user {user.displayName} (ID: {user.id})")
        else:
            logger.warning(f"Failed to ban user {user.displayName} (ID: {user.id})")


def get_file_paths() -> Tuple[str, str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "config.json")
    users_file = os.path.join(script_dir, "crasher_id_dump copy.txt")
    return config_file, users_file


def setup_logging():
    logger.add("vrchat_moderation.log", rotation="1 day")


async def load_config_and_users(
    file_reader: FileReader, config_file: str, users_file: str
) -> Tuple[Config, List[User]]:
    config_task = asyncio.create_task(Config.load_config(file_reader, config_file))
    users_task = asyncio.create_task(
        TextUserLoader(file_reader, users_file).load_users()
    )
    return await config_task, await users_task


def create_api_client(config: Config) -> vrchatapi.ApiClient:
    api_client = vrchatapi.ApiClient(
        vrchatapi.Configuration(
            username=config.username,
            password=config.password,
        )
    )
    api_client.user_agent = (
        "VRChatGroupModerationScript/1.0 (https://github.com/Amoenus/vrchat_autoban)"
    )
    return api_client


def create_vrchat_api(api_client: vrchatapi.ApiClient, config: Config) -> VRChatAPI:
    auth_api = authentication_api.AuthenticationApi(api_client)
    groups_api_instance = groups_api.GroupsApi(api_client)

    authenticator = VRChatAuthenticator(auth_api)
    rate_limiter = ProgressBarRateLimiter(config.rate_limit)
    moderator = VRChatGroupModerator(groups_api_instance, rate_limiter)

    return VRChatAPI(authenticator, moderator)


async def run_moderation(
    api: VRChatAPI, users: List[User], group_id: str
) -> Tuple[pendulum.DateTime, pendulum.DateTime]:
    start_time = pendulum.now()
    logger.info(f"Starting moderation process at {start_time}")

    await moderate_users(api, users, group_id)

    end_time = pendulum.now()
    return start_time, end_time


def log_moderation_results(start_time: pendulum.DateTime, end_time: pendulum.DateTime):
    duration = end_time - start_time
    logger.info(
        f"Moderation process completed at {end_time}. Total duration: {duration}"
    )


async def main():
    config_file, users_file = get_file_paths()
    setup_logging()

    file_reader = AsyncFileReader()
    config, users_to_ban = await load_config_and_users(
        file_reader, config_file, users_file
    )

    api_client = create_api_client(config)
    api = create_vrchat_api(api_client, config)
    api.authenticate()

    start_time, end_time = await run_moderation(api, users_to_ban, config.group_id)
    log_moderation_results(start_time, end_time)


if __name__ == "__main__":
    asyncio.run(main())
