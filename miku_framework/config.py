from pydantic import BaseModel, Field


class FrameworkConfig(BaseModel):
    command_prefixes: list[str] = Field(default=[])
    http_host: str = Field(default="127.0.0.1")
    http_port: int = Field(default=8080)
    http_url: str = Field(default="https://example.com")
