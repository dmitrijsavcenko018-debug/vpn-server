from collections.abc import AsyncGenerator

from .db import async_session


async def get_session() -> AsyncGenerator:
    async with async_session() as session:
        yield session
