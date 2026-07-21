"""
Test d'intégration bout-en-bout pour la source ServiceNow.

Contrairement à test_servicenow_transformer.py (qui teste uniquement la
logique de transformation en isolation), ce fichier valide le pipeline
complet tel qu'il serait exécuté en production :

    ServiceNowConnector.fetch()
        -> ServiceNowTransformer.transform()
        -> Embedder.embed_chunks()
        -> VectorStore.upsert_document_with_chunks()

Aucun appel réseau réel n'est fait : le client HTTP ServiceNow est
remplacé par un faux client (FakeServiceNowClient) qui simule l'API
Table REST, et le VectorStore est remplacé par un faux store en mémoire
(FakeVectorStore) qui capture ce qui aurait été écrit en base.

Cela permet de valider l'intégration du connecteur dans
IngestionPipeline (le même orchestrateur que Jira/Confluence/SharePoint)
sans dépendre de Docker, PostgreSQL ou d'une vraie instance ServiceNow.
"""

from typing import AsyncGenerator, Optional

import pytest

from app.connectors.servicenow.pipeline import ServiceNowConnector
from app.connectors.servicenow.transformer import ServiceNowTransformer
from app.core.models import Chunk
from app.ingestion.embeddings.embedder import Embedder
from app.ingestion.pipeline import IngestionPipeline

FAKE_INCIDENTS = [
    {
        "number": "INC0010001",
        "short_description": "Imprimante RH hors service",
        "description": "L'imprimante du 3e étage n'imprime plus depuis ce matin.",
        "state": "New",
        "priority": "3 - Moderate",
        "category": "Hardware",
        "assigned_to": "",
        "opened_by": "Claire Dubois",
        "sys_created_on": "2026-02-01 08:00:00",
        "sys_updated_on": "2026-02-01 08:00:00",
        "comments": "",
        "work_notes": "",
    },
    {
        "number": "INC0010002",
        "short_description": "Accès VPN refusé",
        "description": "Connexion VPN refusée depuis la mise à jour de sécurité.",
        "state": "In Progress",
        "priority": "1 - Critical",
        "category": "Network",
        "assigned_to": "Alice Martin",
        "opened_by": "Bob Dupont",
        "sys_created_on": "2026-02-01 09:00:00",
        "sys_updated_on": "2026-02-01 09:45:00",
        "comments": (
            "2026-02-01 09:45:00 - Alice Martin (Additional comments)\n"
            "Investigation en cours, retour sous 1h."
        ),
        "work_notes": "",
    },
]


class FakeServiceNowClient:
    """Simule ServiceNowClient sans appel HTTP réel."""

    def __init__(self, records: list[dict]):
        self._records = records
        self.connection_ok = True

    async def fetch_all_records(
        self, table: str, updated_after: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        for record in self._records:
            yield record

    async def test_connection(self) -> bool:
        return self.connection_ok


class FakeEmbeddingBackend:
    """Backend d'embedding déterministe : pas de modèle réel chargé."""

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeVectorStore:
    """Capture en mémoire ce qui aurait été upserté en base."""

    def __init__(self):
        self.upserts: list[tuple[str, str, list[Chunk]]] = []

    async def upsert_document_with_chunks(
        self, source_type: str, document_id: str, chunks: list[Chunk]
    ) -> int:
        self.upserts.append((source_type, document_id, chunks))
        return len(chunks)


@pytest.mark.asyncio
async def test_servicenow_pipeline_end_to_end_success():
    fake_client = FakeServiceNowClient(FAKE_INCIDENTS)
    fake_store = FakeVectorStore()

    pipeline = IngestionPipeline(
        connector=ServiceNowConnector(client=fake_client, table="incident"),
        transformer=ServiceNowTransformer(),
        embedder=Embedder(backend=FakeEmbeddingBackend()),
        store=fake_store,
    )

    result = await pipeline.run()

    assert result.success is True
    assert result.source_type == "servicenow"
    assert result.total_fetched == 2
    assert result.total_documents == 2
    assert result.total_chunks > 0

    # Deux documents distincts ont bien été upsertés
    document_ids = {doc_id for _, doc_id, _ in fake_store.upserts}
    assert document_ids == {"INC0010001", "INC0010002"}

    # Chaque chunk envoyé au store porte bien un embedding et le bon source_type
    for source_type, _, chunks in fake_store.upserts:
        assert source_type == "servicenow"
        for chunk in chunks:
            assert chunk.embedding == [0.1, 0.2, 0.3]
            assert chunk.source_type == "servicenow"


@pytest.mark.asyncio
async def test_servicenow_pipeline_fails_fast_on_bad_connection():
    fake_client = FakeServiceNowClient(FAKE_INCIDENTS)
    fake_client.connection_ok = False
    fake_store = FakeVectorStore()

    pipeline = IngestionPipeline(
        connector=ServiceNowConnector(client=fake_client, table="incident"),
        transformer=ServiceNowTransformer(),
        embedder=Embedder(backend=FakeEmbeddingBackend()),
        store=fake_store,
    )

    result = await pipeline.run()

    assert result.success is False
    assert result.error_message is not None
    assert result.total_fetched == 0
    assert fake_store.upserts == []


@pytest.mark.asyncio
async def test_servicenow_pipeline_incremental_sync_passes_since_to_client():
    captured = {}

    class CapturingClient(FakeServiceNowClient):
        async def fetch_all_records(self, table, updated_after=None):
            captured["table"] = table
            captured["updated_after"] = updated_after
            for record in self._records:
                yield record

    pipeline = IngestionPipeline(
        connector=ServiceNowConnector(client=CapturingClient(FAKE_INCIDENTS), table="incident"),
        transformer=ServiceNowTransformer(),
        embedder=Embedder(backend=FakeEmbeddingBackend()),
        store=FakeVectorStore(),
    )

    await pipeline.run(since="2026-02-01 00:00:00")

    assert captured["table"] == "incident"
    assert captured["updated_after"] == "2026-02-01 00:00:00"
