# -*- coding:utf-8 -*-
from time import time

import gevent
import requests
from gevent import monkey
from lxml import etree

monkey.patch_all()

url = 'https://movie.douban.com/top250'


def fetch_page(url):
    response = requests.get(url)
    return response


def fetch_content(url):
    response = fetch_page(url)
    page = response.content
    return page


def parse(url):
    page = fetch_content(url)
    html = etree.HTML(page)

    xpath_movie = '//*[@id="content"]/div/div[1]/ol/li'
    xpath_title = './/span[@class="title"]'
    xpath_pages = '//*[@id="content"]/div/div[1]/div[2]/a'

    pages = html.xpath(xpath_pages)
    fetch_list = []
    result = []

    for element_movie in html.xpath(xpath_movie):
        result.append(element_movie)

    for p in pages:
        fetch_list.append(url + p.get('href'))

    jobs = [gevent.spawn(fetch_content, url) for url in fetch_list]
    gevent.joinall(jobs)

    for page in [job.value for job in jobs]:
        html = etree.HTML(page)
        for element_movie in html.xpath(xpath_movie):
            result.append(element_movie)

    for i, movie in enumerate(result, 1):
        title = movie.find(xpath_title).text
        print(i, title)


start = time()
parse(url)
end = time()
print('cost %d seconds' % (end - start))
