"""
Connecteur ServiceNow : implémentation concrète de BaseConnector.
Seule classe ServiceNow-spécifique connue du pipeline générique.
"""

from typing import AsyncGenerator, Optional

from app.connectors.servicenow.client import ServiceNowClient
from app.core.base_connector import BaseConnector
from app.core.models import RawRecord
from config import settings


class ServiceNowConnector(BaseConnector):

    def __init__(self, client: Optional[ServiceNowClient] = None, table: Optional[str] = None):
        """
        Args:
            client: instance de ServiceNowClient (injectable pour les tests).
            table: table ServiceNow à synchroniser (ex: 'incident', 'problem').
        """
        self._client = client or ServiceNowClient()
        self._table = table or self._default_table()

    @property
    def source_type(self) -> str:
        return "servicenow"

    @property
    def table(self) -> str:
        return self._table

    async def fetch(self, since: Optional[str] = None) -> AsyncGenerator[RawRecord, None]:
        async for item in self._client.fetch_all_records(self._table, since):
            yield RawRecord(
                source_type=self.source_type,
                record_id=item["number"],
                raw_data=item,
            )

    async def test_connection(self) -> bool:
        return await self._client.test_connection()

    @staticmethod
    def _default_table() -> str:
        if not settings.servicenow_table:
            raise ValueError(
                "Aucune table ServiceNow configurée. "
                "Définissez SERVICENOW_TABLE dans .env, ou passez "
                "table explicitement à ServiceNowConnector()."
            )
        return settings.servicenow_table