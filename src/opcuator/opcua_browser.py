from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from asyncua import Client, ua

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

    if settings.opcua_username:
        client.set_user(settings.opcua_username)
    if settings.opcua_password:
        client.set_password(settings.opcua_password)
    if settings.opcua_security_string:
        await client.set_security_string(settings.opcua_security_string)

    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect()


async def browse_namespace(request: BrowseRequest) -> BrowseResponse:
    endpoint = request.endpoint or settings.opcua_endpoint
    if not endpoint:
        raise OpcUaBrowseError(
            "Missing OPC UA endpoint. Pass endpoint in the request or set OPCUA_ENDPOINT.",
        )

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

    children = await _read_or_empty(node.get_children)
    browsed_children = []
    for child in children:
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
        if include_methods or child_payload.get("node_class") != ua.NodeClass.Method.name:
            browsed_children.append(child_payload)

    if browsed_children:
        payload["children"] = browsed_children

    return payload


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
