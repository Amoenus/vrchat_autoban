import aiofiles


class AsyncFileHandler:
    async def read_file(self, file_path: str) -> str:
        async with aiofiles.open(file_path, "r") as file:
            return await file.read()

    async def write_file(self, file_path: str, content: str):
        async with aiofiles.open(file_path, "w") as file:
            await file.write(content)
