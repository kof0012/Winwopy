import asyncio
import logging
import re
import time
from asyncio import Queue
from urllib import parse

import aiohttp
import pymongo
from fake_useragent import UserAgent

from helloworld.bloom import BloomFilter

logging.basicConfig(level=1)
LOGGER = logging.getLogger(__name__)


class Myasycatch:
    def __init__(self, roots_url, max_tries=4, max_workers=3):
        self.bloom = BloomFilter()
        self.loop = asyncio.get_event_loop()
        self.q = Queue(loop=self.loop)
        self.max_tries = max_tries
        self.roots_url = roots_url
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.max_workers = max_workers
        self.db = pymongo.MongoClient().test
        self.jobs_count = 0
        for root_url in roots_url:
            self.add_url(root_url)

    async def get(url):
        async with  aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as resp:
                return await resp.text(), resp.url

    async def fetch(self, url, proxy=None):
        tries = 0
        ua = UserAgent()
        while tries < self.max_tries:
            try:
                headers = {'User-Agent': ua.random}
                response = await self.session.get(url, proxy=proxy, headers=headers, allow_redirects=False)
                if tries > 1:
                    LOGGER.info('try %r for %r success', tries, url)
                break

            except aiohttp.ClientError as client_error:
                LOGGER.info('try %r for %r raised %r',
                            tries, url, client_error)
            tries += 1

        else:
            LOGGER.error('%r failed after %r tries', url, self.max_tries)
            return

        try:
            if response.status in (403, 500):
                LOGGER.info('403出现 %r,%r', response.status, url)
                getproxy = await self.get_proxy()
                if getproxy:
                    LOGGER.info('使用代理 %r', getproxy)
                    return await self.fetch(url, proxy=getproxy)
                else:
                    LOGGER.info('获取代理失败')
                    return
            else:
                links = await self.parse_url(response)
                for link in links:
                    if not self.bloom.isContains(link):
                        self.add_url(link)

        except:
            await response.release()

    async def parse_url(self, response):
        reg_content = re.findall(r'a.*title.*href=[\'\"](.*?)[\'\"]>(.*?)</a>', await response.text())
        all_url = [parse.urljoin(str(response.url), i[0]) for i in reg_content]
        result = [{"title": o, "url": parse.urljoin(str(response.url), i)} for i, o in reg_content]
        opers = [
            pymongo.UpdateOne({"title": o}, {"$setOnInsert": {"url": parse.urljoin(str(response.url), i)}}, upsert=True)
            for i, o in reg_content]
        jg = self.db.aya.bulk_write(opers)
        # for gg in result:
        #     jg=self.db.aya.update({"title": gg.get("title")}, {"$setOnInsert": {"url": gg.get("url")}}, upsert=True)
        #     print(jg)
        # data=self.db.aya.insert_many(result)
        # LOGGER.info('插入数据库%r条记录',len(data.inserted_ids))
        if jg.upserted_count:
            LOGGER.info('插入数据库%r条记录', jg.upserted_count)
        elif jg.matched_count:
            LOGGER.info('数据库已存在%r条相同记录', jg.matched_count)
        self.jobs_count += 1

        return all_url

    async def get_proxy(self):
        proxy_url = "http://127.0.0.1:5000/get"
        try:
            response = await self.session.get(proxy_url)
            if response.status == 200:
                return await response.text()
            elif response.status == 500:
                LOGGER.info("IPpool iS EMPTY!!!wait 1 min")
                time.sleep(60)
                return await self.get_proxy()

        except:
            return await self.get_proxy()

    def add_url(self, url):
        self.q.put_nowait(url)
        self.bloom.insert(url)
        LOGGER.info('加入url %r', url)

    async def worker(self):
        try:
            while 1:
                url = await self.q.get()
                await self.fetch(url)
                self.q.task_done()
        except asyncio.CancelledError:
            raise NotImplementedError

    async def crawl(self):
        workers = [asyncio.ensure_future(self.worker(), loop=self.loop) for _ in range(self.max_workers)]
        await self.q.join()
        LOGGER.info('队列完成，共计%r', self.jobs_count)
        print('已经停止全部work？', asyncio.gather(*asyncio.Task.all_tasks(loop=self.loop)).cancel())
        print('已经停止aiohttp？', self.session.close())


loop = asyncio.get_event_loop()
begin = Myasycatch(['http://www.jianshu.com/p/b5e347b3a17c', ])
loop.run_until_complete(begin.crawl())
loop.close()
