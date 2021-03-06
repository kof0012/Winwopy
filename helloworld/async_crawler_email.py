import asyncio
import re

import aiohttp

headers = {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
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
mails = set()
sites = set()


async def fetch_content(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            return await response.text()


async def parse_html(url):
    page = await fetch_content(url)
    mails.update(await find_mails(page))
    sites.update(await find_sites(page))
    print(mails)
    task = [asyncio.ensure_future(parse_html(url)) for url in sites]



async def find_mails(string):
    # mails列表
    res = [re.sub(r'\s|mailto:', '', match) for match in
           re.findall(r'[-.\w]+?@[-.\w]+?\.\w+ |mailto:[-.\w]+?@[-.\w]+?\.\w+', string, re.S) if
           not match.endswith(prohibit)]

    return res


async def find_sites(string):
    # urls列表
    res = []
    for match in re.findall(
            r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9]\.[^\s]{2,})',
            string, re.S):
        url = re.sub(r'["\s>]', '', match)
        if not url.endswith(prohibit):
            res.append(url)

    return res


def main():
    tasks = [parse_html(url) for url in
             ('http://www.sohu.com',)]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()


if __name__ == '__main__':
    main()

