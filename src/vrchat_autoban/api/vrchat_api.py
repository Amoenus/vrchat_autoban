from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.api.authenticator import VRChatAuthenticator
from vrchat_autoban.api.moderator import VRChatGroupModerator


class VRChatAPI:
    def __init__(
        self, authenticator: VRChatAuthenticator, moderator: VRChatGroupModerator
    ):
        self.authenticator = authenticator
        self.moderator = moderator

    async def authenticate(self):
        await self.authenticator.authenticate()

    async def ban_user_from_group(self, group_id: str, user_id: str) -> BanStatus:
        return await self.moderator.ban_user(group_id, user_id)
