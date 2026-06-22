from fastapi import FastAPI, HTTPException

from .config import settings
from .models import BrowseRequest, BrowseResponse
from .opcua_browser import OpcUaBrowseError, browse_namespace, get_server_endpoints

app = FastAPI(
    title="OPCUAtor",
    version="0.1.0",
    description="Headless OPC UA probe exposed as a REST service.",
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
        "opcua_application_uri": settings.opcua_application_uri,
        "opcua_security_enabled": bool(settings.opcua_security_string),
        "opcua_max_depth": settings.opcua_max_depth,
        "opcua_max_nodes": settings.opcua_max_nodes,
        "opcua_browse_references_per_node": settings.opcua_browse_references_per_node,
        "opcua_request_timeout": settings.opcua_request_timeout,
    }


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
        return await browse_namespace(request)
    except OpcUaBrowseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OPC UA browse failed: {exc}") from exc


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
