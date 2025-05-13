import json

from loguru import logger
from vrchatapi.api import groups_api
from vrchatapi.exceptions import ApiException
from vrchatapi.models.ban_group_member_request import BanGroupMemberRequest

from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.utils.interfaces import RateLimiter


class VRChatGroupModerator:
    def __init__(
        self,
        groups_api_instance: groups_api.GroupsApi,
        rate_limiter: RateLimiter,
        processed_user_tracker: ProcessedUserTracker,
    ):
        self.groups_api = groups_api_instance
        self.rate_limiter = rate_limiter
        self.processed_user_tracker = processed_user_tracker

    async def ban_user(self, group_id: str, user_id: str) -> BanStatus:
        if self.processed_user_tracker.is_processed(user_id):
            # logger.info(f"User {user_id} already processed. Skipping.") # Already logged by tracker
            return BanStatus.ALREADY_PROCESSED

        try:
            ban_request = BanGroupMemberRequest(user_id=user_id)
            result = self.groups_api.ban_group_member(
                group_id, ban_group_member_request=ban_request
            )
            logger.debug(
                f"Ban API call result for {user_id}: {result}"
            )  # Changed to debug for less verbose success
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.NEWLY_BANNED
        except ApiException as e:
            return await self._handle_ban_exception(e, user_id)

    async def _handle_ban_exception(self, e: ApiException, user_id: str) -> BanStatus:
        error_message = ""
        if e.body:
            try:
                error_body = json.loads(e.body)
                error_message = error_body.get("error", {}).get("message", "")
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse JSON from error body for user {user_id}. Status: {e.status}. Body: {e.body}"
                )
                # Fall through to general error logging

        if e.status == 400 and "User is already banned" in error_message:
            logger.info(f"User {user_id} is already banned. Marking as processed.")
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.ALREADY_BANNED

        # General error logging
        logger.error(
            f"Exception when calling GroupsApi->ban_group_member for user {user_id}: ({e.status}) {e.reason}"
        )
        if error_message:  # Log parsed message if available
            logger.error(f"API Error Message: {error_message}")
        elif e.body:  # Log raw body if not empty and no parsed message
            logger.error(f"Response body: {e.body}")

        await self._apply_rate_limit()  # Wait for rate limit after failed API call
        return BanStatus.FAILED

    async def _apply_rate_limit(self):
        await self.rate_limiter.wait()
