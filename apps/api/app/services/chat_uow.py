"""Chat-specific unit of work for transaction boundaries."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.chat import ChatRepository


class ChatUnitOfWork:
    """Coordinates chat repositories and transaction lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.chat_repository = ChatRepository(session)
        self._committed = False

    async def __aenter__(self) -> ChatUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        del exc
        del tb
        if exc_type is not None:
            await self.rollback()
            return False
        if not self._committed:
            await self.rollback()
        return False

    async def flush(self) -> None:
        """Flush pending ORM changes."""

        await self._session.flush()

    async def commit(self) -> None:
        """Commit transaction changes."""

        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        """Rollback the current transaction."""

        await self._session.rollback()
