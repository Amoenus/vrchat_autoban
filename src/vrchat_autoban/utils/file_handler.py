import aiofiles

from vrchat_autoban.utils.interfaces import FileHandler


class AsyncFileHandler(FileHandler):
    async def read_file(self, file_path: str) -> str:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
            return await file.read()

    async def write_file(self, file_path: str, content: str):
        async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
            await file.write(content)
