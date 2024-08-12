from enum import Enum, auto


class BanStatus(Enum):
    NEWLY_BANNED = auto()
    ALREADY_BANNED = auto()
    ALREADY_PROCESSED = auto()
    FAILED = auto()
