from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    rest_host: str = Field(default="0.0.0.0", validation_alias="REST_HOST")
    rest_port: int = Field(default=9500, validation_alias="REST_PORT")

    opcua_endpoint: str | None = Field(default=None, validation_alias="OPCUA_ENDPOINT")
    opcua_username: str | None = Field(default=None, validation_alias="OPCUA_USERNAME")
    opcua_password: str | None = Field(default=None, validation_alias="OPCUA_PASSWORD")
    opcua_application_uri: str | None = Field(
        default=None,
        validation_alias="OPCUA_APPLICATION_URI",
    )
    opcua_security_string: str | None = Field(
        default=None,
        validation_alias="OPCUA_SECURITY_STRING",
    )

    opcua_max_depth: int = Field(default=8, validation_alias="OPCUA_MAX_DEPTH")
    opcua_max_nodes: int = Field(default=5000, validation_alias="OPCUA_MAX_NODES")
    opcua_request_timeout: float = Field(
        default=30.0,
        validation_alias="OPCUA_REQUEST_TIMEOUT",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
