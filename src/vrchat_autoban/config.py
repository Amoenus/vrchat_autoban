from vrchat_autoban.utils.interfaces import FileHandler


from loguru import logger
from pydantic import BaseModel, Field


import json
import os


class Config(BaseModel):
    username: str
    password: str
    group_id: str
    rate_limit: int = Field(default=60)

    @classmethod
    async def load(cls, file_handler: FileHandler, file_path: str) -> "Config":
        try:
            content = await file_handler.read_file(file_path)
            data = json.loads(content)
            return cls(**data)
        except FileNotFoundError:
            logger.error(
                f"Config file '{file_path}' not found. Current working directory: {os.getcwd()}"
            )
            raise SystemExit(1)
        except json.JSONDecodeError:
            logger.error(
                f"Unable to parse '{file_path}'. Please ensure it's valid JSON."
            )
            raise SystemExit(1)
