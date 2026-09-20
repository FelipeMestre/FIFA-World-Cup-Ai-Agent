from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import bindparam, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
    UpsertResult,
)
from src.infra.postgres.schemas.base import Base


class _SqlAlchemyIngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        schema_cls: type[Base],
        rows: list[dict[str, Any]],
        conflict_columns: Sequence[str],
    ) -> UpsertResult:
        table_name = schema_cls.__tablename__
        if not rows:
            return UpsertResult(table_name=table_name, row_count=0)

        stmt = insert(schema_cls).values(rows)
        update_columns = {
            column.name: stmt.excluded[column.name]
            for column in schema_cls.__table__.columns
            if column.name not in conflict_columns
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=list(conflict_columns),
            set_=update_columns,
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return UpsertResult(table_name=table_name, row_count=len(rows))

    async def has_rows(self, schema_cls: type[Base]) -> bool:
        result = await self._session.execute(select(schema_cls.__table__).limit(1))
        return result.first() is not None

    async def fetch_columns(
        self, schema_cls: type[Base], columns: Sequence[str]
    ) -> list[dict[str, Any]]:
        table = schema_cls.__table__
        result = await self._session.execute(select(*(table.c[name] for name in columns)))
        return [dict(row._mapping) for row in result]

    async def has_non_null_column(self, schema_cls: type[Base], column: str) -> bool:
        table = schema_cls.__table__
        result = await self._session.execute(
            select(table.c[column]).where(table.c[column].isnot(None)).limit(1)
        )
        return result.first() is not None

    async def update_matched(
        self,
        schema_cls: type[Base],
        key_column: str,
        rows: list[dict[str, Any]],
    ) -> UpsertResult:
        table_name = schema_cls.__tablename__
        if not rows:
            return UpsertResult(table_name=table_name, row_count=0)

        table = schema_cls.__table__
        # A plain `key_column` bindparam name collides with the SET clause
        # SQLAlchemy infers from the same-named param key in each row dict,
        # so the WHERE match key travels under a distinct name.
        stmt = update(table).where(table.c[key_column] == bindparam("_match_key"))
        params = [
            {**{k: v for k, v in row.items() if k != key_column}, "_match_key": row[key_column]}
            for row in rows
        ]
        await self._session.execute(stmt, params)
        await self._session.commit()
        return UpsertResult(table_name=table_name, row_count=len(rows))


def get_ingestion_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IngestionRepositoryInterface:
    return _SqlAlchemyIngestionRepository(session)
