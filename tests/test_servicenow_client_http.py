"""
Test de bout en bout "HTTP réel" pour ServiceNowClient.

Contrairement à test_servicenow_pipeline.py (qui mocke le client Python),
ce test lance un vrai serveur HTTP local (fake_servicenow_server.py) et
laisse ServiceNowClient lui parler normalement via httpx — comme il le
ferait avec une vraie instance ServiceNow. Cela valide :
  - la Basic Auth
  - la pagination par sysparm_offset/sysparm_limit
  - le filtre incrémental sysparm_query (sys_updated_on>=...)
  - le parsing de la réponse JSON de l'API Table

Nécessite `uvicorn` (déjà dans requirements.txt du projet).
"""

import asyncio
import threading
import time

import httpx
import pytest
import uvicorn

from app.connectors.servicenow.client import ServiceNowClient
from tests.mocks.fake_servicenow_server import app as fake_app

HOST = "127.0.0.1"
PORT = 9911


@pytest.fixture(scope="module")
def fake_servicenow_server():
    """Démarre le faux serveur ServiceNow dans un thread pour la durée du module."""
    config = uvicorn.Config(fake_app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Attend que le serveur soit prêt à répondre
    for _ in range(50):
        try:
            httpx.get(f"http://{HOST}:{PORT}/api/now/table/sys_user", timeout=0.2)
            break
        except httpx.ConnectError:
            time.sleep(0.1)

    yield f"http://{HOST}:{PORT}"

    server.should_exit = True
    thread.join(timeout=5)


def _make_client(monkeypatch, base_url: str, page_size: int = 2) -> ServiceNowClient:
    monkeypatch.setattr("config.settings.servicenow_instance_url", base_url)
    monkeypatch.setattr("config.settings.servicenow_username", "admin")
    monkeypatch.setattr("config.settings.servicenow_password", "admin")
    monkeypatch.setattr("config.settings.servicenow_page_size", page_size)
    return ServiceNowClient()


@pytest.mark.asyncio
async def test_connection_succeeds_with_valid_credentials(fake_servicenow_server, monkeypatch):
    client = _make_client(monkeypatch, fake_servicenow_server)
    assert await client.test_connection() is True


@pytest.mark.asyncio
async def test_connection_fails_with_invalid_credentials(fake_servicenow_server, monkeypatch):
    client = _make_client(monkeypatch, fake_servicenow_server)
    client.auth = ("admin", "wrong-password")
    assert await client.test_connection() is False


@pytest.mark.asyncio
async def test_fetch_all_records_paginates_across_multiple_pages(
    fake_servicenow_server, monkeypatch
):
    # page_size=2 sur 5 incidents -> doit forcer 3 pages (2 + 2 + 1)
    client = _make_client(monkeypatch, fake_servicenow_server, page_size=2)

    records = [r async for r in client.fetch_all_records("incident")]

    assert len(records) == 5
    numbers = [r["number"] for r in records]
    assert numbers == [
        "INC0010001", "INC0010002", "INC0010003", "INC0010004", "INC0010005",
    ]


@pytest.mark.asyncio
async def test_fetch_all_records_applies_incremental_filter(
    fake_servicenow_server, monkeypatch
):
    client = _make_client(monkeypatch, fake_servicenow_server, page_size=10)

    records = [
        r async for r in client.fetch_all_records(
            "incident", updated_after="2026-02-02 00:00:00"
        )
    ]

    numbers = {r["number"] for r in records}
    assert numbers == {"INC0010004", "INC0010005"}
