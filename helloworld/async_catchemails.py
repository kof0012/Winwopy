"""A simple web crawler -- class implementing crawling logic."""

import asyncio
import cgi
import logging
import re
import time
import urllib.parse
from asyncio import Queue
from collections import namedtuple

import aiohttp
logging.basicConfig(level=1)

LOGGER = logging.getLogger(__name__)


def lenient_host(host):
    parts = host.split('.')[-2:]
    return ''.join(parts)


def is_redirect(response):
    return response.status in (300, 301, 303, 307)


FetchStatistic = namedtuple('FetchStatistic',
                            ['url',
                             'next_url',
                             'status',
                             'exception',
                             'size',
                             'content_type',
                             'encoding',
                             'num_urls',
                             'num_new_urls'])

prohibit = (  # images
    'mng', 'pct', 'bmp', 'gif', 'jpg', 'jpeg', 'png', 'pst', 'psp', 'tif',
    'tiff', 'ai', 'drw', 'dxf', 'eps', 'ps', 'svg',

    # audio
    'mp3', 'wma', 'ogg', 'wav', 'ra', 'aac', 'mid', 'au', 'aiff',

    # video
    '3gp', 'asf', 'asx', 'avi', 'mov', 'mp4', 'mpg', 'qt', 'rm', 'swf', 'wmv',
    'm4a',

    # office suites
    'xls', 'xlsx', 'ppt', 'pptx', 'pps', 'doc', 'docx', 'odt', 'ods', 'odg',
    'odp',

    # other
    'css', 'pdf', 'exe', 'bin', 'rss', 'zip', 'rar', 'py', 'asp', 'php', 'aspx', 'exe')


class Crawler:
    """Crawl a set of URLs.

    This manages two sets of URLs: 'urls' and 'done'.  'urls' is a set of
    URLs seen, and 'done' is a list of FetchStatistics.
    """

    def __init__(self, roots,
                 exclude=None, strict=False,  # What to crawl.
                 max_redirect=5, max_tries=4,  # Per-url limits.
                 max_tasks=100, *, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.roots = roots
        self.exclude = exclude
        self.strict = strict
        self.max_redirect = max_redirect
        self.max_tries = max_tries
        self.max_tasks = max_tasks
        self.q = Queue(loop=self.loop)
        self.seen_urls = set()
        self.done = []
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.root_domains = set()
        self.findmails = set()
        for root in roots:
            parts = urllib.parse.urlparse(root)
            host, port = urllib.parse.splitport(parts.netloc)
            if not host:
                continue
            if re.match(r'\A[\d\.]*\Z', host):
                self.root_domains.add(host)
            else:
                host = host.lower()
                if self.strict:
                    self.root_domains.add(host)
                else:
                    self.root_domains.add(lenient_host(host))
        for root in roots:
            self.add_url(root)
        self.t0 = time.time()
        self.t1 = None

    def close(self):
        """Close resources."""
        self.session.close()

    def host_okay(self, host):
        """Check if a host should be crawled.

        A literal match (after lowercasing) is always good.  For hosts
        that don't look like IP addresses, some approximate matches
        are okay depending on the strict flag.
        """
        host = host.lower()
        if host in self.root_domains:
            return True
        if re.match(r'\A[\d\.]*\Z', host):
            return False
        if self.strict:
            return self._host_okay_strictish(host)
        else:
            return self._host_okay_lenient(host)

    def _host_okay_strictish(self, host):
        """Check if a host should be crawled, strict-ish version.

        This checks for equality modulo an initial 'www.' component.
        """
        host = host[4:] if host.startswith('www.') else 'www.' + host
        return host in self.root_domains

    def _host_okay_lenient(self, host):
        """Check if a host should be crawled, lenient version.

        This compares the last two components of the host.
        """
        return lenient_host(host) in self.root_domains

    def record_statistic(self, fetch_statistic):
        """Record the FetchStatistic for completed / failed URL."""
        self.done.append(fetch_statistic)

    async def parse_links(self, response):
        """Return a FetchStatistic and list of links."""
        links = set()
        content_type = None
        encoding = None
        body = await response.read()

        if response.status == 200:
            content_type = response.headers.get('content-type')
            pdict = {}

            if content_type:
                content_type, pdict = cgi.parse_header(content_type)

            encoding = pdict.get('charset', 'utf-8')
            if content_type in ('text/html', 'application/xml'):
                text = await response.text()

                # Replace href with (?:href|src) to follow image links.
                urls = set(re.findall(r'''(?i)href=["'](https?://[^\s"'<>]+)''',
                                      text))
                if urls:
                    LOGGER.info('got %r distinct urls from %r',
                                len(urls), response.url)
                for url in urls:
                    # normalized = parse.urljoin(response.url, url)
                    deadened, frag = urllib.parse.urldefrag(url)
                    if self.url_allowed(deadened):
                        links.add(deadened)

                new_cathcmails = await self.find_mails(text)
                if new_cathcmails:
                    write_to_txt = new_cathcmails.difference(self.findmails)
                    self.findmails.update(new_cathcmails)
                    LOGGER.info('拿到新email地址 %r', write_to_txt)
                    await self.write(write_to_txt)

        stat = FetchStatistic(
            url=response.url,
            next_url=None,
            status=response.status,
            exception=None,
            size=len(body),
            content_type=content_type,
            encoding=encoding,
            num_urls=len(links),
            num_new_urls=len(links - self.seen_urls))

        return stat, links

    async def fetch(self, url, max_redirect, proxy=None):
        """Fetch one URL."""
        tries = 0
        exception = None
        while tries < self.max_tries:
            try:
                response = await self.session.get(
                    url,  headers={
                        'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'},
                    allow_redirects=False, proxy=proxy)

                if tries > 1:
                    LOGGER.info('try %r for %r success', tries, url)
                break
            except aiohttp.ClientError as client_error:
                LOGGER.info('try %r for %r raised %r',
                            tries, url, client_error)
                exception = client_error

            tries += 1
        else:
            # We never broke out of the loop: all tries failed.
            LOGGER.error('%r failed after %r tries',
                         url, self.max_tries)
            self.record_statistic(FetchStatistic(url=url,
                                                 next_url=None,
                                                 status=None,
                                                 exception=exception,
                                                 size=0,
                                                 content_type=None,
                                                 encoding=None,
                                                 num_urls=0,
                                                 num_new_urls=0))
            return

        try:
            if is_redirect(response):
                location = response.headers['location']
                next_url = urllib.parse.urljoin(url, location)
                self.record_statistic(FetchStatistic(url=url,
                                                     next_url=next_url,
                                                     status=response.status,
                                                     exception=None,
                                                     size=0,
                                                     content_type=None,
                                                     encoding=None,
                                                     num_urls=0,
                                                     num_new_urls=0))

                if next_url in self.seen_urls:
                    return
                if max_redirect > 0:
                    LOGGER.info('redirect to %r from %r', next_url, url)
                    self.add_url(next_url, max_redirect - 1)
                else:
                    LOGGER.error('redirect limit reached for %r from %r',
                                 next_url, url)

            elif response.status in (302, 403):
                LOGGER.info('302,403出现 %r,%r', response.status, url)
                getproxy = await self.get_proxy()
                if getproxy:
                    LOGGER.info('使用代理 %r', getproxy)
                    return await self.fetch(url, max_redirect, proxy=getproxy)
                else:
                    LOGGER.info('获取代理失败')
                    return

            else:
                stat, links = await self.parse_links(response)
                self.record_statistic(stat)

                for link in links.difference(self.seen_urls):
                    self.q.put_nowait((link, self.max_redirect))
                self.seen_urls.update(links)
        except:
            pass
            await response.release()

    async def work(self):
        """Process queue items forever."""
        try:
            while 1:
                url, max_redirect = await self.q.get()
                assert url in self.seen_urls
                await self.fetch(url, max_redirect)

                self.q.task_done()
        except asyncio.CancelledError:
            pass

    def url_allowed(self, url):
        if self.exclude and re.search(self.exclude, url):
            return False
        parts = urllib.parse.urlparse(url)
        if parts.scheme not in ('http', 'https'):
            LOGGER.debug('skipping non-http scheme in %r', url)
            return False
        host, port = urllib.parse.splitport(parts.netloc)
        if not self.host_okay(host):
            LOGGER.debug('skipping non-root host in %r', url)
            return False
        return True

    def add_url(self, url, max_redirect=None):
        """Add a URL to the queue if not seen before."""
        if max_redirect is None:
            max_redirect = self.max_redirect
        LOGGER.debug('adding %r %r', url, max_redirect)
        self.seen_urls.add(url)
        self.q.put_nowait((url, max_redirect))

    async def find_mails(self, string):
        # parse  mails
        res = {re.sub(r'\s|mailto:', '', match) for match in
               re.findall(r'[-.\w]+?@[-.\w]+?\.\w+ |mailto:[-.\w]+?@[-.\w]+?\.\w+', string, re.S) if
               not match.endswith(prohibit)}

        return res

    async def write(self, data):
        with open('e-mail-crawler-master.txt', 'a') as f:
            for iq in data:
                f.write(iq + '\r\n')

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

    async def crawl(self):
        """Run the crawler until all finished."""
        workers = [asyncio.ensure_future(self.work(), loop=self.loop)
                   for _ in range(self.max_tasks)]
        self.t0 = time.time()
        await self.q.join()

        self.t1 = time.time()
        # for w in workers:
        for w in asyncio.Task.all_tasks():
            w.cancel()


# giv tasks and loop
loop = asyncio.get_event_loop()
zhua = Crawler(["https://www.douban.com/group/topic/41562980/?start=500",
                "https://www.douban.com/event/14146775/discussion/40108760/", 'http://tieba.baidu.com/p/3934726472'],
               max_tasks=5, strict=False)

loop.run_until_complete(zhua.crawl())
print('完成了{0}个链接，花费{1:.3f}时间'.format(len(zhua.done), zhua.t1 - zhua.t0))
zhua.close()
loop.close()
