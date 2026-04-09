from __future__ import annotations

import asyncio

MAX_PER_SECOND = 30
DELAY_SEC = 1.0 / MAX_PER_SECOND


async def throttled_send(send_callable, *args, **kwargs):
    # Telegram flood limit guard for burst traffic.
    result = await send_callable(*args, **kwargs)
    await asyncio.sleep(DELAY_SEC)
    return result
