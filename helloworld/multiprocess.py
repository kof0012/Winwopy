import asyncio
import time
from multiprocessing import Pool


class ya:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.q = asyncio.Queue(loop=self.loop)
        for i in range(1, 5):
            self.q.put_nowait(i)

    async def consum(self):
        try:
            while 1:
                val = await self.q.get()
                await asyncio.sleep(2)
                print('拿到', val)
                self.q.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            print('enaa')

    async def main(self):
        works = [asyncio.ensure_future(self.consum(), loop=self.loop)
            , asyncio.ensure_future(self.consum(), loop=self.loop)]

        await self.q.join()
        for w in works:
            w.cancel()


def coro():
    cai = ya()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cai.main())
    loop.close()


def qi_fact(n):
    jg = fact(n)
    time.sleep(4)
    print(jg)


def fact(n):
    if n == 1:
        return 1
    return n * fact(n - 1)


if __name__ == '__main__':
    print('begin process')
    p = Pool(4)
    p.apply_async(qi_fact, args=(60,))
    p.apply_async(coro)
    print("waiting for done")
    p.close()
    p.join()
    print("all done")
