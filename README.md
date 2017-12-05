# Winwopy

aiocrawl.py实现用原生asyncio抓取网页，结果保存到本地Mongodb，结合redis-bloomfilter过滤。
redis使用aioredis，封装到另外一个文档。workers默认3个。
