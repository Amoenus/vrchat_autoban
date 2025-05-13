from typing import Tuple
from vrchat_autoban.api.authenticator import VRChatAuthenticator
from vrchat_autoban.api.moderator import VRChatGroupModerator
from vrchat_autoban.api.user_moderator import VRChatUserModerator
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.models.user_block_status import UserBlockStatus


class VRChatAPI:
    def __init__(
        self,
        authenticator: VRChatAuthenticator,
        group_moderator: VRChatGroupModerator,
        user_moderator: VRChatUserModerator,
    ):
        self.authenticator = authenticator
        self.group_moderator = group_moderator
        self.user_moderator = user_moderator

    async def authenticate(self):
        await self.authenticator.authenticate()

    async def ban_user_from_group(
        self, group_id: str, user_id: str
    ) -> Tuple[BanStatus, str | None]:
        return await self.group_moderator.ban_user(group_id, user_id)

    async def block_user_on_account(self, user_id: str) -> UserBlockStatus:
        return await self.user_moderator.block_user(user_id)
