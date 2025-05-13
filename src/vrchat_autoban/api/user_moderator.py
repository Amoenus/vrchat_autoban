from loguru import logger
from vrchatapi.api import playermoderation_api
from vrchatapi.exceptions import ApiException
from vrchatapi.models import ModerateUserRequest

from vrchat_autoban.data.processed_user_tracker import ProcessedUserTracker
from vrchat_autoban.models.user_block_status import UserBlockStatus
from vrchat_autoban.utils.interfaces import RateLimiter


class VRChatUserModerator:
    def __init__(
        self,
        playmod_api: playermoderation_api.PlayermoderationApi,
        rate_limiter: RateLimiter,
        processed_block_tracker: ProcessedUserTracker,  # Tracker for account blocks
    ):
        self.playmod_api = playmod_api
        self.rate_limiter = rate_limiter
        self.processed_user_tracker = processed_block_tracker

    async def block_user(self, user_id: str) -> UserBlockStatus:
        if self.processed_user_tracker.is_processed(user_id):
            # The is_processed method in ProcessedUserTracker now logs at DEBUG
            # logger.info(f"User {user_id} was already processed for account-blocking by this script.")
            return UserBlockStatus.ALREADY_PROCESSED_BY_SCRIPT

        try:
            # Attempt to block the user directly.
            # This POST request should ensure the user is in a 'blocked' state from your account.
            # If they were already blocked by you, the API typically accepts this without error.
            moderate_request = ModerateUserRequest(moderated=user_id, type="block")
            self.playmod_api.moderate_user(moderate_user_request=moderate_request)

            logger.info(
                f"API call to block user {user_id} successful. User is now account-blocked."
            )
            await self.processed_user_tracker.mark_as_processed(
                user_id
            )  # Mark as processed by this script
            await self.rate_limiter.wait()
            return UserBlockStatus.BLOCK_SUCCESSFUL

        except ApiException as e:
            logger.error(
                f"Failed to account-block user {user_id}: API Exception {e.status} - {e.reason}. Body: {e.body}"
            )
            # Do not mark as processed by script if the block attempt itself failed, so it can be retried.
            await self.rate_limiter.wait()  # Apply rate limit even on failure
            return UserBlockStatus.FAILED_TO_BLOCK
        except Exception as e_block:  # Catch unexpected errors during the block call
            logger.error(
                f"An unexpected error occurred while account-blocking user {user_id}: {e_block}"
            )
            await self.rate_limiter.wait()
            return UserBlockStatus.FAILED_TO_BLOCK
