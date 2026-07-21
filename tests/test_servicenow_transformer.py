from app.connectors.servicenow.transformer import ServiceNowTransformer
from app.core.models import RawRecord

SAMPLE_INCIDENT = {
    "number": "INC0010023",
    "short_description": "Le VPN ne se connecte plus",
    "description": "L'utilisateur ne parvient plus à se connecter au VPN depuis ce matin.",
    "state": "In Progress",
    "priority": "2 - High",
    "category": "Network",
    "assigned_to": "Alice Martin",
    "opened_by": "Bob Dupont",
    "sys_created_on": "2026-01-10 08:15:00",
    "sys_updated_on": "2026-01-10 09:30:00",
    "comments": (
        "2026-01-10 09:30:00 - Alice Martin (Additional comments)\n"
        "Je regarde le souci, je reviens vers vous.\n"
        "\n"
        "2026-01-10 08:20:00 - Bob Dupont (Additional comments)\n"
        "Le VPN affiche une erreur de certificat."
    ),
    "work_notes": (
        "2026-01-10 09:00:00 - Alice Martin (Work notes)\n"
        "Certificat expiré côté serveur, renouvellement en cours."
    ),
}


def _transform(item: dict):
    transformer = ServiceNowTransformer()
    record = RawRecord(source_type="servicenow", record_id=item["number"], raw_data=item)
    return transformer.transform(record)


def test_normalize_extracts_basic_fields():
    normalized = ServiceNowTransformer._normalize(SAMPLE_INCIDENT)

    assert normalized["external_id"] == "INC0010023"
    assert normalized["title"] == "Le VPN ne se connecte plus"
    assert normalized["state"] == "In Progress"
    assert normalized["priority"] == "2 - High"
    assert normalized["assigned_to"] == "Alice Martin"
    assert len(normalized["notes"]) == 3  # 2 comments + 1 work note


def test_transform_creates_body_chunk_with_key_fields():
    chunks = _transform(SAMPLE_INCIDENT)
    body_chunks = [c for c in chunks if c.metadata["chunk_type"] == "body"]

    assert len(body_chunks) >= 1
    content = body_chunks[0].content
    assert "INC0010023" in content
    assert "Le VPN ne se connecte plus" in content
    assert "In Progress" in content
    assert "Alice Martin" in content
    assert body_chunks[0].source_type == "servicenow"
    assert body_chunks[0].document_id == "INC0010023"


def test_transform_creates_one_chunk_per_journal_entry():
    chunks = _transform(SAMPLE_INCIDENT)
    note_chunks = [c for c in chunks if c.metadata["chunk_type"] == "comment"]

    # 2 entrées dans "comments" + 1 dans "work_notes" = 3 chunks
    assert len(note_chunks) == 3
    authors = {c.metadata["note_author"] for c in note_chunks}
    assert authors == {"Alice Martin", "Bob Dupont"}
    assert any(c.metadata["note_kind"] == "Work notes" for c in note_chunks)
    assert any(c.metadata["note_kind"] == "Additional comments" for c in note_chunks)


def test_transform_handles_incident_without_notes():
    item = {**SAMPLE_INCIDENT, "comments": "", "work_notes": None}
    chunks = _transform(item)

    assert all(c.metadata["chunk_type"] == "body" for c in chunks)
    assert len(chunks) >= 1


def test_chunk_ids_are_unique_and_prefixed_by_source():
    chunks = _transform(SAMPLE_INCIDENT)
    chunk_ids = [c.chunk_id for c in chunks]

    assert len(chunk_ids) == len(set(chunk_ids))
    assert all(cid.startswith("servicenow-INC0010023-") for cid in chunk_ids)


def test_long_description_is_split_into_multiple_chunks_with_overlap():
    long_item = {**SAMPLE_INCIDENT, "description": "Phrase test. " * 300}
    chunks = _transform(long_item)
    body_chunks = [c for c in chunks if c.metadata["chunk_type"] == "body"]

    assert len(body_chunks) > 1
    for c in body_chunks:
        assert len(c.content) <= 1500 + 200  # marge liée à l'overlap
