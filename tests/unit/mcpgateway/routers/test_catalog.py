"""Unit tests for the v1 catalog API router."""

# Standard
from unittest.mock import AsyncMock, MagicMock

# Third-Party
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import pytest

# First-Party
from mcpgateway.api.v1 import build_legacy_router, build_v1_router
from mcpgateway.config import settings
from mcpgateway.db import get_db
from mcpgateway.middleware.rbac import get_current_user_with_permissions
from mcpgateway.routers.catalog import list_catalog_servers, router
from mcpgateway.schemas import CatalogListRequest, CatalogListResponse
from tests.helpers.router_helpers import collect_routes


@pytest.fixture
def allow_permission(monkeypatch):
    """Allow RBAC permission checks to pass for decorator-wrapped handlers."""
    mock_perm_service = MagicMock()
    mock_perm_service.check_permission = AsyncMock(return_value=True)
    monkeypatch.setattr("mcpgateway.middleware.rbac.PermissionService", lambda db: mock_perm_service)
    monkeypatch.setattr("mcpgateway.plugins.get_plugin_manager", AsyncMock(return_value=None))
    return mock_perm_service


def _empty_router_kwargs() -> dict[str, APIRouter]:
    """Return the full set of inline-router kwargs as empty APIRouters."""
    names = [
        "protocol_router",
        "tool_router",
        "resource_router",
        "prompt_router",
        "gateway_router",
        "root_router",
        "server_router",
        "metrics_router",
        "tag_router",
        "export_import_router",
        "a2a_router",
    ]
    return {name: APIRouter() for name in names}


def _catalog_client(*, user_dependency=None, db=None) -> TestClient:
    """Mount the production catalog router with controlled dependencies."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/v1")
    if user_dependency is not None:
        test_app.dependency_overrides[get_current_user_with_permissions] = user_dependency
    if db is not None:
        test_app.dependency_overrides[get_db] = lambda: db
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.mark.asyncio
async def test_list_catalog_requires_authenticated_user():
    """Calling the router without an authenticated user returns 401."""
    request = MagicMock(spec=Request)

    with pytest.raises(HTTPException) as exc_info:
        await list_catalog_servers(request, db=MagicMock())

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_list_catalog_disabled_returns_404(monkeypatch, allow_permission):
    """The v1 catalog endpoint returns 404 when the catalog feature is disabled."""
    monkeypatch.setattr("mcpgateway.routers.catalog.settings.mcpgateway_catalog_enabled", False, raising=False)
    request = MagicMock(spec=Request)
    db = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await list_catalog_servers(request, db=db, user={"email": "user@example.com", "db": db})

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Catalog feature is disabled"


@pytest.mark.asyncio
async def test_list_catalog_success_forwards_filters_and_scope(monkeypatch, allow_permission):
    """The v1 catalog endpoint forwards filters and scoped visibility context."""
    monkeypatch.setattr("mcpgateway.routers.catalog.settings.mcpgateway_catalog_enabled", True, raising=False)
    monkeypatch.setattr("mcpgateway.routers.catalog.get_scoped_resource_access_context", MagicMock(return_value=("user@example.com", ["team-a"])))
    mock_response = CatalogListResponse(servers=[], total=0, categories=[], auth_types=[], providers=[], all_tags=[])
    mock_get_catalog = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("mcpgateway.routers.catalog.catalog_service.get_catalog_servers", mock_get_catalog)
    request = MagicMock(spec=Request)
    db = MagicMock()

    result = await list_catalog_servers(
        request,
        category="Development",
        auth_type="OAuth2.1",
        provider="IBM",
        search="github",
        tags=["git", "repo"],
        show_registered_only=True,
        show_available_only=False,
        limit=25,
        offset=50,
        db=db,
        user={"email": "user@example.com", "db": db, "token_teams": ["team-a"]},
    )

    assert result == mock_response
    catalog_request = mock_get_catalog.await_args.args[0]
    assert catalog_request.category == "Development"
    assert catalog_request.auth_type == "OAuth2.1"
    assert catalog_request.provider == "IBM"
    assert catalog_request.search == "github"
    assert catalog_request.tags == ["git", "repo"]
    assert catalog_request.show_registered_only is True
    assert catalog_request.show_available_only is False
    assert catalog_request.limit == 25
    assert catalog_request.offset == 50
    assert mock_get_catalog.await_args.args[1] is db
    assert mock_get_catalog.await_args.kwargs == {"user_email": "user@example.com", "token_teams": ["team-a"]}


def test_catalog_router_is_v1_only():
    """Catalog is exposed at /v1/catalog without creating a legacy /catalog alias."""
    v1_paths = [path for path, *_ in collect_routes(build_v1_router(settings, **_empty_router_kwargs()))]
    legacy_paths = [path for path, *_ in collect_routes(build_legacy_router(settings, **_empty_router_kwargs()))]

    assert "/v1/catalog" in v1_paths
    assert "/v1/catalog/" in v1_paths
    assert "/catalog" not in legacy_paths
    assert "/catalog/" not in legacy_paths


def test_catalog_http_unauthenticated_returns_401(monkeypatch):
    """The mounted route rejects unauthenticated callers."""

    async def reject_authentication():
        raise HTTPException(status_code=401, detail="Not authenticated")

    monkeypatch.setattr("mcpgateway.routers.catalog.settings.mcpgateway_catalog_enabled", True, raising=False)
    response = _catalog_client(user_dependency=reject_authentication, db=MagicMock()).get("/v1/catalog")

    assert response.status_code == 401


def test_catalog_http_insufficient_permission_returns_403(monkeypatch):
    """The mounted route enforces servers.read through the RBAC decorator."""
    mock_perm_service = MagicMock()
    mock_perm_service.check_permission = AsyncMock(return_value=False)
    monkeypatch.setattr("mcpgateway.middleware.rbac.PermissionService", lambda db: mock_perm_service)
    monkeypatch.setattr("mcpgateway.plugins.get_plugin_manager", AsyncMock(return_value=None))

    async def authenticated_user():
        return {"email": "viewer@example.com", "db": MagicMock(), "is_admin": False}

    response = _catalog_client(user_dependency=authenticated_user, db=MagicMock()).get("/v1/catalog")

    assert response.status_code == 403


def test_catalog_http_disabled_returns_404(monkeypatch, allow_permission):
    """The mounted route hides the catalog when its feature flag is disabled."""
    monkeypatch.setattr("mcpgateway.routers.catalog.settings.mcpgateway_catalog_enabled", False, raising=False)

    async def authenticated_user():
        return {"email": "user@example.com", "db": MagicMock(), "is_admin": False}

    response = _catalog_client(user_dependency=authenticated_user, db=MagicMock()).get("/v1/catalog")

    assert response.status_code == 404
    assert response.json() == {"detail": "Catalog feature is disabled"}


def test_catalog_http_parses_query_parameters(monkeypatch, allow_permission):
    """FastAPI parses every catalog query parameter and serializes the response model."""
    monkeypatch.setattr("mcpgateway.routers.catalog.settings.mcpgateway_catalog_enabled", True, raising=False)
    monkeypatch.setattr("mcpgateway.routers.catalog.get_scoped_resource_access_context", MagicMock(return_value=("user@example.com", ["team-a"])))
    mock_response = CatalogListResponse(servers=[], total=0, categories=[], auth_types=[], providers=[], all_tags=[])
    mock_get_catalog = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("mcpgateway.routers.catalog.catalog_service.get_catalog_servers", mock_get_catalog)

    async def authenticated_user():
        return {"email": "user@example.com", "db": MagicMock(), "is_admin": False}

    response = _catalog_client(user_dependency=authenticated_user, db=MagicMock()).get(
        "/v1/catalog",
        params=[
            ("category", "Development"),
            ("auth_type", "OAuth2.1"),
            ("provider", "IBM"),
            ("search", "github"),
            ("tags", "git"),
            ("tags", "repo"),
            ("show_registered_only", "true"),
            ("show_available_only", "false"),
            ("limit", "25"),
            ("offset", "50"),
        ],
    )

    assert response.status_code == 200
    assert response.json() == mock_response.model_dump(mode="json")
    catalog_request = mock_get_catalog.await_args.args[0]
    assert catalog_request == CatalogListRequest(
        category="Development",
        auth_type="OAuth2.1",
        provider="IBM",
        search="github",
        tags=["git", "repo"],
        show_registered_only=True,
        show_available_only=False,
        limit=25,
        offset=50,
    )


def test_catalog_http_scopes_registration_state_per_caller(monkeypatch, allow_permission):
    """Two callers cannot share or observe another team's registration state."""
    fake_catalog = {
        "catalog_servers": [
            {
                "id": "team-server",
                "name": "Team Server",
                "url": "http://team-server",
                "category": "Development",
                "auth_type": "Open",
                "provider": "IBM",
                "tags": [],
                "description": "Team-scoped server",
            }
        ]
    }
    db = MagicMock()
    db.execute.return_value = [("http://team-server", True, None, None, "team", "team-a", "owner@example.com")]
    mock_cache = AsyncMock()
    mock_cache.hash_filters = MagicMock(return_value="shared-hash")
    monkeypatch.setattr("mcpgateway.routers.catalog.settings.mcpgateway_catalog_enabled", True, raising=False)
    monkeypatch.setattr("mcpgateway.routers.catalog.catalog_service.load_catalog", AsyncMock(return_value=fake_catalog))
    monkeypatch.setattr("mcpgateway.routers.catalog.catalog_service._get_registry_cache", MagicMock(return_value=mock_cache))
    monkeypatch.setattr(
        "mcpgateway.routers.catalog.get_scoped_resource_access_context",
        lambda request, _user: ("user@example.com", [request.headers["x-test-team"]]),
    )

    async def authenticated_user():
        return {"email": "user@example.com", "db": db, "is_admin": False}

    client = _catalog_client(user_dependency=authenticated_user, db=db)
    visible = client.get("/v1/catalog", headers={"x-test-team": "team-a"})
    hidden = client.get("/v1/catalog", headers={"x-test-team": "team-b"})

    assert visible.status_code == 200
    assert hidden.status_code == 200
    assert visible.json()["servers"][0]["is_registered"] is True
    assert hidden.json()["servers"][0]["is_registered"] is False
    mock_cache.get.assert_not_called()
    mock_cache.set.assert_not_called()
