from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    rest_host: str = Field(default="0.0.0.0", validation_alias="REST_HOST")
    rest_port: int = Field(default=9500, validation_alias="REST_PORT")

    opcua_endpoint: str | None = Field(default=None, validation_alias="OPCUA_ENDPOINT")
    opcua_username: str | None = Field(default=None, validation_alias="OPCUA_USERNAME")
    opcua_password: str | None = Field(default=None, validation_alias="OPCUA_PASSWORD")
    opcua_application_name: str = Field(
        default="OPCUAtor",
        validation_alias="OPCUA_APPLICATION_NAME",
    )
    opcua_application_uri: str | None = Field(
        default=None,
        validation_alias="OPCUA_APPLICATION_URI",
    )
    opcua_product_uri: str = Field(
        default="urn:opcuator:client",
        validation_alias="OPCUA_PRODUCT_URI",
    )
    opcua_server_uri: str | None = Field(
        default=None,
        validation_alias="OPCUA_SERVER_URI",
    )
    opcua_security_string: str | None = Field(
        default=None,
        validation_alias="OPCUA_SECURITY_STRING",
    )
    opcua_assume_anonymous_if_no_tokens: bool = Field(
        default=True,
        validation_alias="OPCUA_ASSUME_ANONYMOUS_IF_NO_TOKENS",
    )

    opcua_max_depth: int = Field(default=8, validation_alias="OPCUA_MAX_DEPTH")
    opcua_max_nodes: int = Field(default=5000, validation_alias="OPCUA_MAX_NODES")
    opcua_browse_references_per_node: int = Field(
        default=1000,
        validation_alias="OPCUA_BROWSE_REFERENCES_PER_NODE",
    )
    opcua_request_timeout: float = Field(
        default=30.0,
        validation_alias="OPCUA_REQUEST_TIMEOUT",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
