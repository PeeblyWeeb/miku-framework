from pydantic import BaseModel, Field


class FrameworkConfig(BaseModel):
    command_prefixes: list[str] = Field(default=[])
