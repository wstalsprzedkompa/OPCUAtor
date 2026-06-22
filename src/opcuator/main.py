from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from .config import settings
from .connection import connection_manager
from .models import BrowseRequest, BrowseResponse, TreeResponse
from .opcua_browser import (
    OpcUaBrowseError,
    browse_namespace,
    browse_namespace_with_client,
    browse_tree,
    browse_tree_with_client,
    get_server_endpoints,
    render_tree_text,
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


@app.get("/endpoints")
async def endpoints(endpoint: str | None = None) -> dict[str, str | list[dict]]:
    try:
        return {
            "endpoint": endpoint or settings.opcua_endpoint or "",
            "endpoints": await get_server_endpoints(endpoint),
        }
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OPC UA endpoint discovery failed: {exc}") from exc


@app.post("/browse", response_model=BrowseResponse)
async def browse(request: BrowseRequest) -> BrowseResponse:
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


async def _tree_response(request: BrowseRequest) -> TreeResponse:
    if settings.opcua_persistent_connection and request.endpoint is None:
        client = await connection_manager.get_client()
        return await browse_tree_with_client(client, request)
    return await browse_tree(request)


@app.get("/tree", response_model=TreeResponse)
async def tree(
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
        raise HTTPException(status_code=502, detail=f"OPC UA tree browse failed: {exc}") from exc


@app.get("/tree/text")
async def tree_text(
    endpoint: str | None = None,
    root_node: str = "i=84",
    max_depth: int | None = None,
    max_nodes: int | None = None,
    include_methods: bool = True,
) -> Response:
    tree_response = await tree(
        endpoint=endpoint,
        root_node=root_node,
        max_depth=max_depth,
        max_nodes=max_nodes,
        include_methods=include_methods,
    )
    return Response(render_tree_text(tree_response.tree), media_type="text/plain")


@app.get("/namespace", response_model=BrowseResponse)
async def namespace(
    endpoint: str | None = None,
    root_node: str = "i=85",
    max_depth: int | None = None,
    max_nodes: int | None = None,
    include_values: bool = False,
    include_methods: bool = True,
) -> BrowseResponse:
    return await browse(
        BrowseRequest(
            endpoint=endpoint,
            root_node=root_node,
            max_depth=max_depth,
            max_nodes=max_nodes,
            include_values=include_values,
            include_methods=include_methods,
        ),
    )
