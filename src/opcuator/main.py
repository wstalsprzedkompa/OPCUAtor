from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from .config import settings
from .connection import connection_manager
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
from .opcua_browser import (
    OpcUaBrowseError,
    browse_namespace,
    browse_namespace_with_client,
    browse_tree,
    browse_tree_with_client,
    call_node_method,
    call_node_method_with_client,
    get_server_endpoints,
    read_node_value,
    read_node_value_with_client,
    render_tree_text,
    write_node_value,
    write_node_value_with_client,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.opcua_connect_on_startup:
        try:
            await connection_manager.connect()
        except Exception as exc:
            print(f"OPCUAtor startup connection failed: {exc}")
    try:
        yield
    finally:
        await connection_manager.disconnect()


app = FastAPI(
    title="OPCUAtor",
    version="0.1.0",
    description="OPC UA client with a REST API.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "configured_endpoint": bool(settings.opcua_endpoint),
    }


@app.get("/config")
async def config() -> dict[str, str | int | float | bool | None]:
    return {
        "rest_host": settings.rest_host,
        "rest_port": settings.rest_port,
        "opcua_endpoint": settings.opcua_endpoint,
        "opcua_username": settings.opcua_username,
        "opcua_application_name": settings.opcua_application_name,
        "opcua_application_uri": settings.opcua_application_uri,
        "opcua_product_uri": settings.opcua_product_uri,
        "opcua_server_uri": settings.opcua_server_uri,
        "opcua_security_enabled": bool(settings.opcua_security_string),
        "opcua_assume_anonymous_if_no_tokens": settings.opcua_assume_anonymous_if_no_tokens,
        "opcua_persistent_connection": settings.opcua_persistent_connection,
        "opcua_connect_on_startup": settings.opcua_connect_on_startup,
        "opcua_max_depth": settings.opcua_max_depth,
        "opcua_max_nodes": settings.opcua_max_nodes,
        "opcua_browse_references_per_node": settings.opcua_browse_references_per_node,
        "opcua_request_timeout": settings.opcua_request_timeout,
    }


@app.get("/connection")
async def connection() -> dict[str, str | bool | None]:
    return connection_manager.status().__dict__


@app.post("/connect")
async def connect() -> dict[str, str | bool | None]:
    try:
        return (await connection_manager.connect()).__dict__
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OPC UA connect failed: {exc}") from exc


@app.post("/disconnect")
async def disconnect() -> dict[str, str | bool | None]:
    return (await connection_manager.disconnect()).__dict__


@app.get("/endpoints", include_in_schema=False)
async def endpoints(endpoint: str | None = None) -> dict[str, str | list[dict]]:
    return await get_endpoints(endpoint)


@app.get("/GetEndpoints")
async def get_endpoints(endpoint: str | None = None) -> dict[str, str | list[dict]]:
    try:
        return {
            "endpoint": endpoint or settings.opcua_endpoint or "",
            "endpoints": await get_server_endpoints(endpoint),
        }
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OPC UA endpoint discovery failed: {exc}") from exc


async def _browse_response(request: BrowseRequest) -> BrowseResponse:
    try:
        if settings.opcua_persistent_connection and request.endpoint is None:
            client = await connection_manager.get_client()
            return await browse_namespace_with_client(client, request)
        return await browse_namespace(request)
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if settings.opcua_persistent_connection and request.endpoint is None:
            await connection_manager.reset_after_error(exc)
        raise HTTPException(status_code=502, detail=f"OPC UA browse failed: {exc}") from exc


async def _read_response(request: ReadRequest) -> ReadResponse:
    try:
        if settings.opcua_persistent_connection and request.endpoint is None:
            client = await connection_manager.get_client()
            return await read_node_value_with_client(client, request)
        return await read_node_value(request)
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if settings.opcua_persistent_connection and request.endpoint is None:
            await connection_manager.reset_after_error(exc)
        raise HTTPException(status_code=502, detail=f"OPC UA read failed: {exc}") from exc


async def _write_response(request: WriteRequest) -> WriteResponse:
    try:
        if settings.opcua_persistent_connection and request.endpoint is None:
            client = await connection_manager.get_client()
            return await write_node_value_with_client(client, request)
        return await write_node_value(request)
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if settings.opcua_persistent_connection and request.endpoint is None:
            await connection_manager.reset_after_error(exc)
        raise HTTPException(status_code=502, detail=f"OPC UA write failed: {exc}") from exc


async def _call_response(request: CallRequest) -> CallResponse:
    try:
        if settings.opcua_persistent_connection and request.endpoint is None:
            client = await connection_manager.get_client()
            return await call_node_method_with_client(client, request)
        return await call_node_method(request)
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if settings.opcua_persistent_connection and request.endpoint is None:
            await connection_manager.reset_after_error(exc)
        raise HTTPException(status_code=502, detail=f"OPC UA call failed: {exc}") from exc


@app.post("/Browse", response_model=BrowseResponse)
async def browse_post(request: BrowseRequest) -> BrowseResponse:
    return await _browse_response(request)


@app.get("/Browse", response_model=BrowseResponse)
async def browse_get(
    endpoint: str | None = None,
    root_node: str = "i=85",
    max_depth: int | None = None,
    max_nodes: int | None = None,
    include_values: bool = False,
    include_methods: bool = True,
) -> BrowseResponse:
    return await _browse_response(
        BrowseRequest(
            endpoint=endpoint,
            root_node=root_node,
            max_depth=max_depth,
            max_nodes=max_nodes,
            include_values=include_values,
            include_methods=include_methods,
        ),
    )


@app.post("/Read", response_model=ReadResponse)
async def read_post(request: ReadRequest) -> ReadResponse:
    return await _read_response(request)


@app.get("/Read", response_model=ReadResponse)
async def read_get(node_id: str, endpoint: str | None = None) -> ReadResponse:
    return await _read_response(ReadRequest(endpoint=endpoint, node_id=node_id))


@app.post("/Write", response_model=WriteResponse)
async def write_post(request: WriteRequest) -> WriteResponse:
    return await _write_response(request)


@app.post("/Call", response_model=CallResponse)
async def call_post(request: CallRequest) -> CallResponse:
    return await _call_response(request)


async def _tree_response(request: BrowseRequest) -> TreeResponse:
    if settings.opcua_persistent_connection and request.endpoint is None:
        client = await connection_manager.get_client()
        return await browse_tree_with_client(client, request)
    return await browse_tree(request)


@app.get("/Browse/Hierarchy", response_model=TreeResponse)
async def browse_hierarchy_get(
    endpoint: str | None = None,
    root_node: str = "i=84",
    max_depth: int | None = None,
    max_nodes: int | None = None,
    include_methods: bool = True,
) -> TreeResponse:
    try:
        return await _tree_response(
            BrowseRequest(
                endpoint=endpoint,
                root_node=root_node,
                max_depth=max_depth,
                max_nodes=max_nodes,
                include_values=False,
                include_methods=include_methods,
            ),
        )
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        if settings.opcua_persistent_connection and endpoint is None:
            await connection_manager.reset_after_error(exc)
        raise HTTPException(status_code=502, detail=f"OPC UA hierarchy browse failed: {exc}") from exc


@app.get("/Browse/Tree")
async def browse_tree_get(
    endpoint: str | None = None,
    root_node: str = "i=84",
    max_depth: int | None = None,
    max_nodes: int | None = None,
    include_methods: bool = True,
) -> Response:
    tree_response = await browse_hierarchy_get(
        endpoint=endpoint,
        root_node=root_node,
        max_depth=max_depth,
        max_nodes=max_nodes,
        include_methods=include_methods,
    )
    return Response(render_tree_text(tree_response.tree), media_type="text/plain")
