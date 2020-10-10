import random
from typing import Optional

import aiohttp
from simple_avk import SimpleAVK


class VKWorker(SimpleAVK):

    def __init__(
            self, aiohttp_session: aiohttp.ClientSession,
            message_symbols_limit: Optional[int] = 4096) -> None:
        super().__init__(aiohttp_session)
        self.message_symbols_limit = message_symbols_limit

    async def reply(self, peer_id: int, text: str) -> None:
        if self.message_symbols_limit:
            text_parts = (
                text[i:i + self.message_symbols_limit]
                for i in range(
                    0,
                    len(text),
                    self.message_symbols_limit
                )
            )
        else:
            text_parts = [text]
        for part in text_parts:
            await self.call_method(
                "messages.send",
                {
                    "peer_id": peer_id,
                    "text": part,
                    "random_id": random.randint(-1_000_000, 1_000_000)
                }
            )
