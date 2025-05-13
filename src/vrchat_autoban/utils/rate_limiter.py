import asyncio

from tqdm import tqdm


class ProgressBarRateLimiter:
    def __init__(self, limit: int):
        self.limit = limit

    async def wait(self):
        with tqdm(total=self.limit, desc="Rate limit", unit="s", leave=False) as pbar:
            for _ in range(self.limit):
                await asyncio.sleep(1)
                pbar.update(1)
