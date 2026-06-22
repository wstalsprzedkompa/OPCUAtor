from pydantic import BaseModel, Field


class BrowseRequest(BaseModel):
    endpoint: str | None = Field(
        default=None,
        description="OPC UA endpoint URL. If omitted, OPCUA_ENDPOINT is used.",
    )
    root_node: str = Field(
        default="i=85",
        description="NodeId where browsing starts. i=85 is the standard Objects folder.",
    )
    max_depth: int | None = Field(default=None, ge=0, le=50)
    max_nodes: int | None = Field(default=None, ge=1, le=100000)
    include_values: bool = Field(
        default=False,
        description="Read current values for variable nodes when possible.",
    )
    include_methods: bool = Field(
        default=True,
        description="Include OPC UA method nodes visible in the browsed tree.",
    )


class BrowseResponse(BaseModel):
    endpoint: str
    root_node: str
    node_count: int
    truncated: bool
    namespace_array: list[str]
    tree: dict
