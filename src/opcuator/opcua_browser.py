from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

from asyncua import Client, Node, ua

from .config import settings
from .models import BrowseRequest, BrowseResponse


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

    client.name = settings.opcua_application_name
    client.description = settings.opcua_application_name
    client.product_uri = settings.opcua_product_uri
    if settings.opcua_application_uri:
        client.application_uri = settings.opcua_application_uri
    if settings.opcua_server_uri:
        client.server_uri = settings.opcua_server_uri
    if settings.opcua_username:
        client.set_user(settings.opcua_username)
    if settings.opcua_password:
        client.set_password(settings.opcua_password)
    security_string = _normalize_security_string(settings.opcua_security_string)
    if security_string:
        await client.set_security_string(security_string)

    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect()


async def browse_namespace(request: BrowseRequest) -> BrowseResponse:
    endpoint = _normalize_endpoint(request.endpoint or settings.opcua_endpoint)

    max_depth = request.max_depth if request.max_depth is not None else settings.opcua_max_depth
    max_nodes = request.max_nodes if request.max_nodes is not None else settings.opcua_max_nodes
    counter = {"count": 0, "truncated": False}

    async with _connected_client(endpoint) as client:
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
        endpoint=endpoint,
        root_node=request.root_node,
        node_count=counter["count"],
        truncated=counter["truncated"],
        namespace_array=namespace_array,
        tree=tree,
    )


async def get_server_endpoints(endpoint: str | None = None) -> list[dict[str, Any]]:
    normalized_endpoint = _normalize_endpoint(endpoint or settings.opcua_endpoint)
    client = Client(url=normalized_endpoint, timeout=settings.opcua_request_timeout)
    client.name = settings.opcua_application_name
    client.description = settings.opcua_application_name
    client.product_uri = settings.opcua_product_uri
    if settings.opcua_application_uri:
        client.application_uri = settings.opcua_application_uri
    if settings.opcua_server_uri:
        client.server_uri = settings.opcua_server_uri
    endpoints = await client.connect_and_get_server_endpoints()
    return [_endpoint_to_json(item) for item in endpoints]


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
            f"Invalid OPC UA endpoint '{value}'. Host and port are required, for example: opc.tcp://192.168.1.50:4840",
        )

    return value


def _normalize_security_string(security_string: str | None) -> str | None:
    value = (security_string or "").strip()
    if value.lower() in {"", "none", "none_", "securitypolicy#none"}:
        return None
    return value


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


async def _read_namespace_array(client: Client) -> list[str]:
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
