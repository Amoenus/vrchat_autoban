from pydantic import BaseModel, Field


class User(BaseModel):
    id: str
    displayName: str = Field(alias="display_name")
