from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from logging import Logger, getLogger
from typing import Any

from pyodbc import Cursor, Error as DBError, Row


logger: Logger = getLogger(__name__)

CEISA_TABLE = 'dbo.Ceisa'


class PIBStatus(Enum):
    CEISA_NOT_FOUND = 0
    CEISA_DOWNLOADED = 1
    MAIN_DOC_MISSING = 2
    SP_UPLOADED = 3


@dataclass
class PIBData:
    folder_id: str
    no_aju: str
    type: str
    trx_date: date
    bill_code: str
    bill_total: Decimal


class PIBTask:
    def __init__(
        self,
        data: PIBData,
        status: PIBStatus,
        cursor: Cursor,
    ) -> None:
        self._status = status
        self.data = data
        self.cursor = cursor

    def _db_get(self, column: str) -> Any:
        query: str = f"""
            SELECT {column} FROM {CEISA_TABLE} 
            WHERE NoAJU ? AND FolderID = ?
        """
        params = (self.data.no_aju, self.data.folder_id)
        return self.cursor.execute(query, params).fetchval()

    def _db_update(self, mapping: dict[str, Any]) -> None:
        columns: str = ', '.join([f'[{col}] = ?' for col in mapping.keys()])

        query: str = f"""
            UPDATE {CEISA_TABLE}
            SET LastRunDate = SYSDATETIME(), {columns}
            WHERE NoAJU = ? AND FolderID = ?
        """
        params: list[Any] = list(mapping.values()) + [self.data.no_aju, self.data.folder_id]
        try:
            self.cursor.execute(query, params)
            self.cursor.commit()
        except DBError:
            self.cursor.rollback()

    @property
    def status(self) -> PIBStatus:
        return self._status

    @status.setter
    def status(self, value: PIBStatus) -> None:
        self._db_update({'Status': value.value})
        self._status = value


def get_tasks(cursor: Cursor, count: int = 100) -> list[PIBTask]:
    logger.info('Fetching tasks...')

    query: str = f"""
        SELECT TOP({count}) * FROM {CEISA_TABLE} 
        WHERE [Status] IN (
            {PIBStatus.CEISA_DOWNLOADED.value},
            {PIBStatus.MAIN_DOC_MISSING.value}
        )
        ORDER BY [Status] ASC, TglTrx DESC
    """
    rows: list[Row] = cursor.execute(query).fetchall()

    tasks: list[PIBTask] = []
    for row in rows:
        task = PIBTask(
            PIBData(
                row.FolderID,
                row.NoAJU,
                row.Type,
                row.TglTrx,
                row.BillingDJBCKodeBilling,
                row.BillingDJBCTotalAmount
            ),
            row.Status,
            cursor
        )
        tasks.append(task)

    logger.info(f'    OK: {len(tasks)} fetched')
    return tasks
    