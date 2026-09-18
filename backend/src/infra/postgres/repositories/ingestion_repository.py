from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import Depends
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


def get_ingestion_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IngestionRepositoryInterface:
    return _SqlAlchemyIngestionRepository(session)
