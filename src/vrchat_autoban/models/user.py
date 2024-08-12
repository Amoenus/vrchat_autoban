from pydantic import BaseModel, Field


class User(BaseModel):
    id: str
    display_name: str = Field(alias="name")
