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
            return BanStatus.ALREADY_PROCESSED

        try:
            ban_request = BanGroupMemberRequest(user_id=user_id)
            self.groups_api.ban_group_member(
                group_id, ban_group_member_request=ban_request
            )
            logger.debug(f"Ban API call successful for {user_id}")
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.NEWLY_BANNED
        except ApiException as e:
            return await self._handle_ban_exception(e, user_id, group_id)

    async def _handle_ban_exception(
        self, e: ApiException, user_id: str, group_id: str
    ) -> BanStatus:
        error_message_from_body = ""
        parsed_body = {}

        if e.body:
            try:
                parsed_body = json.loads(e.body)
                # Try to extract a meaningful message from common error structures
                if isinstance(parsed_body.get("error"), dict):
                    error_message_from_body = parsed_body.get("error", {}).get(
                        "message", ""
                    )
                elif isinstance(parsed_body.get("message"), str):
                    error_message_from_body = parsed_body.get("message", "")
                elif isinstance(
                    parsed_body.get("detail"), str
                ):  # FastAPI often uses "detail"
                    error_message_from_body = parsed_body.get("detail", "")
                else:  # Fallback for other JSON structures
                    error_message_from_body = str(parsed_body) if parsed_body else ""
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse JSON from error body for user {user_id} (Status: {e.status}). Raw body: {e.body}"
                )
                error_message_from_body = e.body  # Use raw body if not JSON

        # Specific handling for 400 "User is already banned"
        # VRChat API might return: {"error":{"message":"User is already banned from group!","status_code":400}}
        if e.status == 400 and (
            "user is already banned" in error_message_from_body.lower()
            or "already banned from group" in error_message_from_body.lower()
        ):
            logger.info(
                f"User {user_id} is already banned in group {group_id}. Marking as processed."
            )
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.ALREADY_BANNED

        # Specific handling for 404 "User not Found"
        # VRChat API might return: {"error":{"message":"User not found","status_code":404}}
        # Or as seen in user log: "User <user_id> not Found" likely parsed from a similar structure
        if e.status == 404:
            normalized_error_msg = error_message_from_body.lower()
            # Check for general "user not found" or specific "user <id> not found"
            if (
                "user not found" in normalized_error_msg
                or f"user {user_id.lower()} not found" in normalized_error_msg
            ):
                logger.info(
                    f"User {user_id} not found (API status 404). Likely deleted by VRChat. Marking as processed."
                )
                await self.processed_user_tracker.mark_as_processed(user_id)
                await self._apply_rate_limit()
                return (
                    BanStatus.ALREADY_PROCESSED
                )  # Treat as successfully handled for our purposes

        # General error logging for unhandled cases
        log_context = (
            f"Exception when attempting to ban user {user_id} from group {group_id}: "
            f"HTTP {e.status} - {e.reason}."
        )
        if (
            error_message_from_body and error_message_from_body != e.body
        ):  # Prefer parsed message
            logger.error(f"{log_context} API Error Message: {error_message_from_body}")
        elif e.body:  # Fallback to raw body if no better message or parsing failed
            logger.error(f"{log_context} Response Body: {e.body}")
        else:  # No body
            logger.error(log_context)

        await self._apply_rate_limit()
        return BanStatus.FAILED

    async def _apply_rate_limit(self):
        await self.rate_limiter.wait()
