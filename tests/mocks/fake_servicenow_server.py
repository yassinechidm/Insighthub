"""
Faux serveur ServiceNow — simule /api/now/table/{table} (Table REST API).

But : permettre un test de bout en bout RÉEL du ServiceNowClient (vrais
appels HTTP via httpx, vraie pagination, vraie Basic Auth) sans avoir
besoin d'une instance ServiceNow (developer instance) déjà provisionnée.

Lancement :
    uvicorn tests.mocks.fake_servicenow_server:app --port 9999

Puis, dans .env (ou variables d'environnement) :
    SERVICENOW_INSTANCE_URL=http://localhost:9999
    SERVICENOW_USERNAME=admin
    SERVICENOW_PASSWORD=admin
    SERVICENOW_TABLE=incident
    SERVICENOW_PAGE_SIZE=2

Ce serveur reproduit volontairement les points qui font souvent
"casser" une intégration ServiceNow réelle :
  - Basic Auth obligatoire (401 sinon)
  - Pagination par sysparm_offset / sysparm_limit
  - Filtre sysparm_query minimal : "sys_updated_on>=<date>"
  - sysparm_display_value=true : les champs référence sont déjà en texte
"""

import base64
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query

app = FastAPI(title="Fake ServiceNow Table API")

VALID_USER = "admin"
VALID_PASSWORD = "admin"

# Jeu de données de démo — 5 incidents, volontairement variés
# (avec/sans commentaires, priorités différentes) pour exercer tous les
# chemins du transformer.
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
        "work_notes": (
            "2026-02-01 09:10:00 - Alice Martin (Work notes)\n"
            "Certificat client expiré, renouvellement en cours."
        ),
    },
    {
        "number": "INC0010003",
        "short_description": "Boîte mail pleine",
        "description": "L'utilisateur ne reçoit plus d'emails depuis hier.",
        "state": "Resolved",
        "priority": "4 - Low",
        "category": "Messaging",
        "assigned_to": "Karim Idrissi",
        "opened_by": "Fatima Ezzahra",
        "sys_created_on": "2026-01-30 14:00:00",
        "sys_updated_on": "2026-01-31 10:00:00",
        "comments": "",
        "work_notes": (
            "2026-01-31 10:00:00 - Karim Idrissi (Work notes)\n"
            "Quota augmenté à 5 Go, résolu."
        ),
    },
    {
        "number": "INC0010004",
        "short_description": "Écran bleu au démarrage",
        "description": "Le poste redémarre en boucle après une mise à jour Windows.",
        "state": "New",
        "priority": "2 - High",
        "category": "Hardware",
        "assigned_to": "",
        "opened_by": "Youssef Amrani",
        "sys_created_on": "2026-02-02 07:30:00",
        "sys_updated_on": "2026-02-02 07:30:00",
        "comments": "",
        "work_notes": "",
    },
    {
        "number": "INC0010005",
        "short_description": "Demande d'accès à un dossier partagé",
        "description": "Besoin d'un accès en lecture/écriture au dossier 'Finance/2026'.",
        "state": "In Progress",
        "priority": "3 - Moderate",
        "category": "Access",
        "assigned_to": "Alice Martin",
        "opened_by": "Sara Benali",
        "sys_created_on": "2026-02-02 08:00:00",
        "sys_updated_on": "2026-02-02 08:05:00",
        "comments": "",
        "work_notes": "",
    },
]


def _check_auth(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(status_code=401, detail="Basic auth requise")

    decoded = base64.b64decode(authorization.removeprefix("Basic ")).decode()
    user, _, password = decoded.partition(":")
    if user != VALID_USER or password != VALID_PASSWORD:
        raise HTTPException(status_code=401, detail="Identifiants invalides")


@app.get("/api/now/table/sys_user")
def sys_user(
    sysparm_limit: int = Query(1),
    authorization: Optional[str] = Header(None),
):
    """Utilisé par ServiceNowClient.test_connection()."""
    _check_auth(authorization)
    return {"result": [{"sys_id": "fake-admin-id", "user_name": "admin"}][:sysparm_limit]}


@app.get("/api/now/table/{table}")
def table_records(
    table: str,
    sysparm_query: str = Query(""),
    sysparm_limit: int = Query(100),
    sysparm_offset: int = Query(0),
    sysparm_fields: str = Query(""),
    sysparm_display_value: str = Query("true"),
    sysparm_exclude_reference_link: str = Query("true"),
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)

    if table != "incident":
        return {"result": []}

    records = FAKE_INCIDENTS

    # Filtre minimal : "sys_updated_on>=YYYY-MM-DD HH:MM:SS^ORDERBY..."
    if "sys_updated_on>=" in sysparm_query:
        threshold = sysparm_query.split("sys_updated_on>=", 1)[1].split("^", 1)[0]
        records = [r for r in records if r["sys_updated_on"] >= threshold]

    page = records[sysparm_offset: sysparm_offset + sysparm_limit]
    return {"result": page}
