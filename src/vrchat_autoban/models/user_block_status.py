# src/vrchat_autoban/models/user_block_status.py
from enum import Enum, auto


class UserBlockStatus(Enum):
    BLOCK_SUCCESSFUL = auto()
    ALREADY_PROCESSED_BY_SCRIPT = auto()
    FAILED_TO_BLOCK = auto()
