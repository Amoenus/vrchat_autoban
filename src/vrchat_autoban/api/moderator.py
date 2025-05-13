import json
from typing import Tuple, Optional

from loguru import logger
from vrchatapi.api import groups_api
from vrchatapi.exceptions import ApiException
from vrchatapi.models import (
    BanGroupMemberRequest,
    GroupMember,
)  # Assuming GroupMember is the response type

from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.models.ban_status import BanStatus
from vrchat_autoban.utils.interfaces import RateLimiter


class VRChatGroupModerator:
    def __init__(
        self,
        groups_api_instance: groups_api.GroupsApi,
        rate_limiter: RateLimiter,
        processed_group_ban_tracker: ProcessedUserTracker,
    ):
        self.groups_api = groups_api_instance
        self.rate_limiter = rate_limiter
        self.processed_user_tracker = processed_group_ban_tracker

    async def ban_user(
        self, group_id: str, user_id: str
    ) -> Tuple[BanStatus, Optional[str]]:
        actual_display_name: Optional[str] = None
        if self.processed_user_tracker.is_processed(user_id):
            # This log is now handled by is_processed itself if it's configured to log
            return BanStatus.ALREADY_PROCESSED, None

        try:
            ban_request = BanGroupMemberRequest(user_id=user_id)
            result: GroupMember = self.groups_api.ban_group_member(  # type: ignore
                group_id, ban_group_member_request=ban_request
            )
            logger.debug(
                f"Group ban API call for {user_id} successful. Raw Response: {result}"
            )

            if result and hasattr(result, "user"):
                user_details_from_api = getattr(result, "user", None)
                if user_details_from_api and hasattr(
                    user_details_from_api, "displayName"
                ):
                    fetched_name = getattr(user_details_from_api, "displayName", None)
                    if isinstance(fetched_name, str) and fetched_name.strip():
                        actual_display_name = fetched_name.strip()
                        logger.info(
                            f"Extracted display name '{actual_display_name}' for user ID {user_id} from group ban response."
                        )
                    elif fetched_name is not None:
                        logger.warning(
                            f"Successfully group-banned user ID {user_id}. 'displayName' in API response user object is present but not a valid non-empty string (value: '{fetched_name}'). User object: {user_details_from_api}"
                        )
                    else:
                        logger.warning(
                            f"Successfully group-banned user ID {user_id}. 'displayName' attribute in API response user object is None. User object: {user_details_from_api}"
                        )
                elif user_details_from_api:
                    logger.warning(
                        f"Successfully group-banned user ID {user_id}. User object found in API response but 'displayName' attribute is missing. User object: {user_details_from_api}"
                    )
                else:
                    logger.warning(
                        f"Successfully group-banned user ID {user_id}. The 'user' object within the API response was None. Response: {result}"
                    )
            else:
                logger.warning(
                    f"Successfully group-banned user ID {user_id}, but the 'user' attribute was not found in the API response as expected. Response: {result}"
                )

            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.NEWLY_BANNED, actual_display_name
        except ApiException as e:
            ban_status_on_exception = await self._handle_ban_exception(
                e, user_id, group_id
            )
            return ban_status_on_exception, None
        except AttributeError as ae:
            logger.error(
                f"AttributeError while processing group ban response for {user_id}: {ae}. This might indicate an unexpected API response structure."
            )
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.NEWLY_BANNED, None
        except Exception as ex_general:
            logger.error(
                f"Unexpected general error during group ban or display name extraction for {user_id}: {ex_general}"
            )
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.NEWLY_BANNED, None

    async def _handle_ban_exception(
        self, e: ApiException, user_id: str, group_id: str
    ) -> BanStatus:
        error_message_from_body = ""
        parsed_body = {}

        if e.body:
            try:
                parsed_body = json.loads(e.body)
                if isinstance(parsed_body.get("error"), dict):
                    error_message_from_body = parsed_body.get("error", {}).get(
                        "message", ""
                    )
                elif isinstance(parsed_body.get("message"), str):
                    error_message_from_body = parsed_body.get("message", "")
                elif isinstance(parsed_body.get("detail"), str):
                    error_message_from_body = parsed_body.get("detail", "")
                else:
                    error_message_from_body = str(parsed_body) if parsed_body else ""
            except json.JSONDecodeError:
                logger.debug(  # Changed to debug as main will log failure
                    f"Failed to parse JSON from error body for user {user_id} (Status: {e.status}). Raw body: {e.body}"
                )
                error_message_from_body = e.body

        if e.status == 400 and (
            "user is already banned" in error_message_from_body.lower()
            or "already banned from group" in error_message_from_body.lower()
        ):
            logger.info(
                f"User {user_id} is already banned in group {group_id} (API status {e.status}). Marking as processed for group ban."
            )
            await self.processed_user_tracker.mark_as_processed(user_id)
            await self._apply_rate_limit()
            return BanStatus.ALREADY_BANNED

        if e.status == 404:
            normalized_error_msg = error_message_from_body.lower()
            if (
                "user not found" in normalized_error_msg
                or f"user {user_id.lower()} not found" in normalized_error_msg
            ):
                logger.info(
                    f"User {user_id} not found (API status 404 for group ban). Likely deleted by VRChat. Marking as processed for group ban."
                )
                await self.processed_user_tracker.mark_as_processed(user_id)
                await self._apply_rate_limit()
                return BanStatus.ALREADY_PROCESSED

        log_context = (
            f"Exception when attempting to group-ban user {user_id} from group {group_id}: "
            f"HTTP {e.status} - {e.reason}."
        )
        if error_message_from_body and error_message_from_body != e.body:
            logger.error(f"{log_context} API Error Message: {error_message_from_body}")
        elif e.body:
            logger.error(f"{log_context} Response Body: {e.body}")
        else:
            logger.error(log_context)

        await self._apply_rate_limit()
        return BanStatus.FAILED

    async def _apply_rate_limit(self):
        await self.rate_limiter.wait()
