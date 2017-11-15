import asyncio
from asyncio import Queue
class Test:
    def __init__(self):
        self.que = Queue()
        self.pue = Queue()
    async def consumer(self):
        while True:
            try:
                print('consumer', await self.que.get())
            finally:
                try:
                    self.que.task_done()
                except ValueError:
                    if self.que.empty():
                        print("que empty")
    async def work(self):
        while True:
            try:
                value = await self.pue.get()
                print('producer', value)
                await self.que.put(value)
            finally:
                try:
                    self.pue.task_done()
                except ValueError:
                    if self.pue.empty():
                        print("pue empty")
    async def run(self):
        await asyncio.wait([self.pue.put(i) for i in range(10)])
        tasks = [asyncio.ensure_future(self.work())]
        tasks.append(asyncio.ensure_future(self.consumer()))
        print('p queue join')
        await self.pue.join()
        print('p queue is done & q queue join')
        await self.que.join()
        print('q queue is done')
        for task in tasks:
            task.cancel()
if __name__ == '__main__':
    print('----start----')
    case = Test()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(case.run())
    print('----end----')