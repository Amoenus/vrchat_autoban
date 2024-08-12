from typing import Protocol


class FileHandler(Protocol):
    async def read_file(self, file_path: str) -> str: ...
    async def write_file(self, file_path: str, content: str): ...


class RateLimiter(Protocol):
    async def wait(self): ...
