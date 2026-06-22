from typing import Any

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
    namespace_array: list[str | None]
    tree: dict


class TreeResponse(BaseModel):
    endpoint: str
    root_node: str
    node_count: int
    truncated: bool
    tree: dict


class ReadRequest(BaseModel):
    endpoint: str | None = Field(
        default=None,
        description="OPC UA endpoint URL. If omitted, OPCUA_ENDPOINT is used.",
    )
    node_id: str = Field(description="NodeId to read, for example ns=2;s=Some.Node")


class ReadResponse(BaseModel):
    endpoint: str
    node_id: str
    value: Any


class WriteRequest(BaseModel):
    endpoint: str | None = Field(
        default=None,
        description="OPC UA endpoint URL. If omitted, OPCUA_ENDPOINT is used.",
    )
    node_id: str = Field(description="NodeId to write, for example ns=2;s=Some.Node")
    value: Any = Field(description="JSON value to write.")
    variant_type: str | None = Field(
        default=None,
        description="Optional OPC UA VariantType name, for example Boolean, Int32, String, Double.",
    )


class WriteResponse(BaseModel):
    endpoint: str
    node_id: str
    written: bool
    value: Any
    variant_type: str | None


class CallRequest(BaseModel):
    endpoint: str | None = Field(
        default=None,
        description="OPC UA endpoint URL. If omitted, OPCUA_ENDPOINT is used.",
    )
    object_node_id: str = Field(description="Object NodeId that owns the method.")
    method_node_id: str = Field(description="Method NodeId to call.")
    arguments: list[Any] = Field(default_factory=list)
    argument_types: list[str | None] | None = Field(
        default=None,
        description="Optional OPC UA VariantType names matching arguments.",
    )


class CallResponse(BaseModel):
    endpoint: str
    object_node_id: str
    method_node_id: str
    result: Any
