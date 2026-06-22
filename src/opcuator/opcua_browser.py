from __future__ import annotations

import types
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from asyncua import Client, Node, ua

from .config import settings
from .models import (
    BrowseRequest,
    BrowseResponse,
    CallRequest,
    CallResponse,
    ReadRequest,
    ReadResponse,
    TreeResponse,
    WriteRequest,
    WriteResponse,
)


class OpcUaBrowseError(RuntimeError):
    pass


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = getattr(value, "Text", None)
    if text is not None:
        return text
    name = getattr(value, "Name", None)
    if name is not None:
        return name
    return str(value)


def _node_id_to_json(node_id: ua.NodeId) -> dict[str, Any]:
    return {
        "node_id": node_id.to_string(),
        "namespace_index": node_id.NamespaceIndex,
        "identifier": _variant_to_json(node_id.Identifier),
        "identifier_type": node_id.NodeIdType.name,
    }


def _qualified_name_to_json(value: ua.QualifiedName | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "name": value.Name,
        "namespace_index": value.NamespaceIndex,
    }


def _expanded_node_id_to_string(value: ua.ExpandedNodeId | ua.NodeId) -> str:
    if hasattr(value, "to_nodeid"):
        return value.to_nodeid().to_string()
    return value.to_string()


def _variant_to_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_variant_to_json(item) for item in value]
    if hasattr(value, "to_string"):
        return value.to_string()
    return str(value)


@asynccontextmanager
async def _connected_client(endpoint: str):
    client = Client(url=endpoint, timeout=settings.opcua_request_timeout)
    await configure_client(client)

    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect()


async def browse_namespace(request: BrowseRequest) -> BrowseResponse:
    endpoint = _normalize_endpoint(request.endpoint or settings.opcua_endpoint)
    async with _connected_client(endpoint) as client:
        return await browse_namespace_with_client(client, request, endpoint)


async def browse_namespace_with_client(
    client: Client,
    request: BrowseRequest,
    endpoint: str | None = None,
) -> BrowseResponse:
    response_endpoint = endpoint or get_configured_endpoint()

    max_depth = request.max_depth if request.max_depth is not None else settings.opcua_max_depth
    max_nodes = request.max_nodes if request.max_nodes is not None else settings.opcua_max_nodes
    counter = {"count": 0, "truncated": False}

    namespace_array = await _read_namespace_array(client)
    root = client.get_node(request.root_node)
    tree = await _browse_node(
        root,
        depth=0,
        max_depth=max_depth,
        max_nodes=max_nodes,
        counter=counter,
        include_values=request.include_values,
        include_methods=request.include_methods,
    )

    return BrowseResponse(
        endpoint=response_endpoint,
        root_node=request.root_node,
        node_count=counter["count"],
        truncated=counter["truncated"],
        namespace_array=namespace_array,
        tree=tree,
    )


async def browse_tree(request: BrowseRequest) -> TreeResponse:
    endpoint = _normalize_endpoint(request.endpoint or settings.opcua_endpoint)
    async with _connected_client(endpoint) as client:
        return await browse_tree_with_client(client, request, endpoint)


async def browse_tree_with_client(
    client: Client,
    request: BrowseRequest,
    endpoint: str | None = None,
) -> TreeResponse:
    namespace = await browse_namespace_with_client(client, request, endpoint)
    return TreeResponse(
        endpoint=namespace.endpoint,
        root_node=namespace.root_node,
        node_count=namespace.node_count,
        truncated=namespace.truncated,
        tree=_compact_tree(namespace.tree),
    )


def render_tree_text(tree: dict) -> str:
    lines: list[str] = []
    _render_tree_node(tree, lines, depth=0, is_last=True)
    return "\n".join(lines)


async def get_server_endpoints(endpoint: str | None = None) -> list[dict[str, Any]]:
    normalized_endpoint = _normalize_endpoint(endpoint or settings.opcua_endpoint)
    client = Client(url=normalized_endpoint, timeout=settings.opcua_request_timeout)
    await configure_client(client)
    endpoints = await client.connect_and_get_server_endpoints()
    return [_endpoint_to_json(item) for item in endpoints]


async def read_node_value(request: ReadRequest) -> ReadResponse:
    endpoint = _normalize_endpoint(request.endpoint or settings.opcua_endpoint)
    async with _connected_client(endpoint) as client:
        return await read_node_value_with_client(client, request, endpoint)


async def read_node_value_with_client(
    client: Client,
    request: ReadRequest,
    endpoint: str | None = None,
) -> ReadResponse:
    response_endpoint = endpoint or get_configured_endpoint()
    node = client.get_node(request.node_id)
    value = await node.read_value()
    return ReadResponse(
        endpoint=response_endpoint,
        node_id=request.node_id,
        value=_variant_to_json(value),
    )


async def write_node_value(request: WriteRequest) -> WriteResponse:
    endpoint = _normalize_endpoint(request.endpoint or settings.opcua_endpoint)
    async with _connected_client(endpoint) as client:
        return await write_node_value_with_client(client, request, endpoint)


async def write_node_value_with_client(
    client: Client,
    request: WriteRequest,
    endpoint: str | None = None,
) -> WriteResponse:
    response_endpoint = endpoint or get_configured_endpoint()
    node = client.get_node(request.node_id)
    variant_type = _variant_type_from_name(request.variant_type)
    value = _coerce_variant_value(request.value, variant_type)
    await node.write_value(value, variant_type)
    return WriteResponse(
        endpoint=response_endpoint,
        node_id=request.node_id,
        written=True,
        value=_variant_to_json(value),
        variant_type=variant_type.name if variant_type is not None else None,
    )


async def call_node_method(request: CallRequest) -> CallResponse:
    endpoint = _normalize_endpoint(request.endpoint or settings.opcua_endpoint)
    async with _connected_client(endpoint) as client:
        return await call_node_method_with_client(client, request, endpoint)


async def call_node_method_with_client(
    client: Client,
    request: CallRequest,
    endpoint: str | None = None,
) -> CallResponse:
    response_endpoint = endpoint or get_configured_endpoint()
    object_node = client.get_node(request.object_node_id)
    method_node_id = ua.NodeId.from_string(request.method_node_id)
    arguments = _coerce_arguments(request.arguments, request.argument_types)
    result = await object_node.call_method(method_node_id, *arguments)
    return CallResponse(
        endpoint=response_endpoint,
        object_node_id=request.object_node_id,
        method_node_id=request.method_node_id,
        result=_variant_to_json(result),
    )


def _compact_tree(node: dict[str, Any]) -> dict[str, Any]:
    children = [_compact_tree(child) for child in node.get("children", [])]
    node_class = node.get("node_class")
    method = node_class == ua.NodeClass.Method.name
    name = _tree_node_name(node)
    return {
        "name": name,
        "label": f"*{name}" if method else name,
        "node_id": node.get("node_id"),
        "node_class": node_class,
        "kind": _tree_node_kind(node_class),
        "method": method,
        "children_count": len(children),
        "children": children,
    }


def _tree_node_name(node: dict[str, Any]) -> str:
    display_name = node.get("display_name")
    if display_name:
        return display_name

    browse_name = node.get("browse_name")
    if isinstance(browse_name, dict) and browse_name.get("name"):
        return browse_name["name"]

    return node.get("node_id", "<unknown>")


def _tree_node_kind(node_class: str | None) -> str:
    if node_class == ua.NodeClass.Method.name:
        return "method"
    if node_class == ua.NodeClass.Object.name:
        return "object"
    if node_class == ua.NodeClass.Variable.name:
        return "variable"
    if node_class == ua.NodeClass.ObjectType.name:
        return "object_type"
    if node_class == ua.NodeClass.VariableType.name:
        return "variable_type"
    if node_class == ua.NodeClass.ReferenceType.name:
        return "reference_type"
    if node_class == ua.NodeClass.DataType.name:
        return "data_type"
    if node_class == ua.NodeClass.View.name:
        return "view"
    return "unknown"


def _render_tree_node(node: dict[str, Any], lines: list[str], *, depth: int, is_last: bool) -> None:
    label = node.get("label") or node.get("name") or node.get("node_id") or "<unknown>"

    if depth == 0:
        lines.append(label)
    else:
        connector = "`--" if is_last else "|--"
        lines.append(f"{'   ' * (depth - 1)}{connector} {label}")

    children = node.get("children", [])
    for index, child in enumerate(children):
        _render_tree_node(child, lines, depth=depth + 1, is_last=index == len(children) - 1)


async def configure_client(client: Client) -> None:
    client.name = settings.opcua_application_name
    client.description = settings.opcua_application_name
    client.product_uri = settings.opcua_product_uri
    if settings.opcua_application_uri:
        client.application_uri = settings.opcua_application_uri
    if settings.opcua_server_uri:
        client.server_uri = settings.opcua_server_uri
    if settings.opcua_assume_anonymous_if_no_tokens:
        _allow_missing_anonymous_token_policy(client)
    if settings.opcua_username:
        client.set_user(settings.opcua_username)
    if settings.opcua_password:
        client.set_password(settings.opcua_password)
    security_string = _normalize_security_string(settings.opcua_security_string)
    if security_string:
        await client.set_security_string(security_string)


def get_configured_endpoint() -> str:
    return _normalize_endpoint(settings.opcua_endpoint)


def _normalize_endpoint(endpoint: str | None) -> str:
    value = (endpoint or "").strip()
    if not value:
        raise OpcUaBrowseError(
            "Missing OPC UA endpoint. Pass endpoint in the request or set OPCUA_ENDPOINT.",
        )

    parsed = urlparse(value)
    if parsed.scheme != "opc.tcp":
        raise OpcUaBrowseError(
            f"Invalid OPC UA endpoint '{value}'. Expected format: opc.tcp://HOST:PORT",
        )
    if not parsed.hostname or parsed.port is None:
        raise OpcUaBrowseError(
            f"Invalid OPC UA endpoint '{value}'. Host and port are required, for example: opc.tcp://server-host:4840/OPCUA/Server",
        )

    return value


def _normalize_security_string(security_string: str | None) -> str | None:
    value = (security_string or "").strip()
    if value.lower() in {"", "none", "none_", "securitypolicy#none"}:
        return None
    return value


def _variant_type_from_name(name: str | None) -> ua.VariantType | None:
    value = (name or "").strip()
    if not value:
        return None
    try:
        return ua.VariantType[value]
    except KeyError as exc:
        valid_names = ", ".join(item.name for item in ua.VariantType)
        raise OpcUaBrowseError(f"Unknown variant_type '{value}'. Valid values: {valid_names}") from exc


def _coerce_arguments(values: list[Any], type_names: list[str | None] | None) -> list[Any]:
    if type_names is not None and len(type_names) != len(values):
        raise OpcUaBrowseError("argument_types length must match arguments length.")
    coerced = []
    for index, value in enumerate(values):
        variant_type = _variant_type_from_name(type_names[index] if type_names is not None else None)
        coerced_value = _coerce_variant_value(value, variant_type)
        if variant_type is not None:
            coerced.append(ua.Variant(coerced_value, variant_type))
        else:
            coerced.append(coerced_value)
    return coerced


def _coerce_variant_value(value: Any, variant_type: ua.VariantType | None) -> Any:
    if variant_type is None:
        return value
    if variant_type == ua.VariantType.Boolean:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
            raise OpcUaBrowseError(f"Cannot convert '{value}' to Boolean.")
        return bool(value)
    if variant_type in {
        ua.VariantType.SByte,
        ua.VariantType.Byte,
        ua.VariantType.Int16,
        ua.VariantType.UInt16,
        ua.VariantType.Int32,
        ua.VariantType.UInt32,
        ua.VariantType.Int64,
        ua.VariantType.UInt64,
    }:
        return int(value)
    if variant_type in {ua.VariantType.Float, ua.VariantType.Double}:
        return float(value)
    if variant_type == ua.VariantType.String:
        return str(value)
    if variant_type == ua.VariantType.NodeId:
        return ua.NodeId.from_string(str(value))
    if variant_type == ua.VariantType.QualifiedName:
        if isinstance(value, dict):
            return ua.QualifiedName(value.get("name", ""), int(value.get("namespace_index", 0)))
        return ua.QualifiedName.from_string(str(value))
    return value


def _allow_missing_anonymous_token_policy(client: Client) -> None:
    original_server_policy = client.server_policy

    def server_policy_with_anonymous_fallback(self, token_type: ua.UserTokenType) -> ua.UserTokenPolicy:
        if not self._policy_ids and token_type == ua.UserTokenType.Anonymous:
            return ua.UserTokenPolicy(
                PolicyId="",
                TokenType=ua.UserTokenType.Anonymous,
                SecurityPolicyUri=self.security_policy.URI,
            )
        return original_server_policy(token_type)

    client.server_policy = types.MethodType(server_policy_with_anonymous_fallback, client)


def _endpoint_to_json(endpoint) -> dict[str, Any]:
    return {
        "endpoint_url": endpoint.EndpointUrl,
        "security_mode": endpoint.SecurityMode.name,
        "security_policy_uri": endpoint.SecurityPolicyUri,
        "security_level": endpoint.SecurityLevel,
        "server_application_uri": endpoint.Server.ApplicationUri,
        "server_product_uri": endpoint.Server.ProductUri,
        "server_application_name": _safe_text(endpoint.Server.ApplicationName),
        "user_identity_tokens": [
            {
                "policy_id": token.PolicyId,
                "token_type": token.TokenType.name,
                "security_policy_uri": token.SecurityPolicyUri,
            }
            for token in endpoint.UserIdentityTokens
        ],
    }


async def _read_namespace_array(client: Client) -> list[str | None]:
    try:
        namespace_node = client.get_node(ua.NodeId(ua.ObjectIds.Server_NamespaceArray))
        value = await namespace_node.read_value()
        return list(value)
    except Exception:
        return []


async def _browse_node(
    node,
    *,
    depth: int,
    max_depth: int,
    max_nodes: int,
    counter: dict[str, Any],
    include_values: bool,
    include_methods: bool,
) -> dict[str, Any]:
    if counter["count"] >= max_nodes:
        counter["truncated"] = True
        return {"truncated": True}

    counter["count"] += 1
    node_class = await _read_or_none(node.read_node_class)

    payload: dict[str, Any] = {
        **_node_id_to_json(node.nodeid),
        "browse_name": _qualified_name_to_json(await _read_or_none(node.read_browse_name)),
        "display_name": _safe_text(await _read_or_none(node.read_display_name)),
        "description": _safe_text(await _read_or_none(node.read_description)),
        "node_class": node_class.name if node_class is not None else None,
        "children": [],
    }

    if include_values and node_class == ua.NodeClass.Variable:
        payload["value"] = _variant_to_json(await _read_or_none(node.read_value))

    if depth >= max_depth:
        payload["children_truncated_by_depth"] = True
        return payload

    children = await _browse_child_references(node)
    browsed_children = []
    for child, reference in children:
        if counter["count"] >= max_nodes:
            counter["truncated"] = True
            break
        child_payload = await _browse_node(
            child,
            depth=depth + 1,
            max_depth=max_depth,
            max_nodes=max_nodes,
            counter=counter,
            include_values=include_values,
            include_methods=include_methods,
        )
        _merge_reference_data(child_payload, reference)
        if include_methods or child_payload.get("node_class") != ua.NodeClass.Method.name:
            browsed_children.append(child_payload)

    if browsed_children:
        payload["children"] = browsed_children

    return payload


async def _browse_child_references(node) -> list[tuple[Any, ua.ReferenceDescription]]:
    references = await _browse_references(node)
    return [(Node(node.session, reference.NodeId), reference) for reference in references]


async def _browse_references(node) -> list[ua.ReferenceDescription]:
    desc = ua.BrowseDescription()
    desc.NodeId = node.nodeid
    desc.BrowseDirection = ua.BrowseDirection.Forward
    desc.ReferenceTypeId = ua.NodeId(ua.ObjectIds.HierarchicalReferences)
    desc.IncludeSubtypes = True
    desc.NodeClassMask = ua.NodeClass.Unspecified
    desc.ResultMask = (
        ua.BrowseResultMask.ReferenceTypeId
        | ua.BrowseResultMask.IsForward
        | ua.BrowseResultMask.NodeClass
        | ua.BrowseResultMask.BrowseName
        | ua.BrowseResultMask.DisplayName
        | ua.BrowseResultMask.TypeDefinition
    )

    params = ua.BrowseParameters()
    params.View.Timestamp = ua.get_win_epoch()
    params.NodesToBrowse.append(desc)
    params.RequestedMaxReferencesPerNode = settings.opcua_browse_references_per_node

    results = await node.session.browse(params)
    if not results:
        return []

    result = results[0]
    references = list(result.References)
    while result.ContinuationPoint:
        next_params = ua.BrowseNextParameters()
        next_params.ContinuationPoints = [result.ContinuationPoint]
        next_params.ReleaseContinuationPoints = False
        next_results = await node.session.browse_next(next_params)
        if not next_results:
            break
        result = next_results[0]
        references.extend(result.References)

    return references


def _merge_reference_data(payload: dict[str, Any], reference: ua.ReferenceDescription) -> None:
    payload["node_id"] = _expanded_node_id_to_string(reference.NodeId)
    payload["browse_name"] = _qualified_name_to_json(reference.BrowseName)
    payload["display_name"] = _safe_text(reference.DisplayName)
    payload["node_class"] = reference.NodeClass.name
    payload["reference_type_id"] = reference.ReferenceTypeId.to_string()
    payload["type_definition"] = _expanded_node_id_to_string(reference.TypeDefinition)


async def _read_or_none(callable_obj):
    try:
        return await callable_obj()
    except Exception:
        return None


async def _read_or_empty(callable_obj):
    try:
        return await callable_obj()
    except Exception:
        return []
