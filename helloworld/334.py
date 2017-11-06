import gevent
import requests
from gevent import monkey
from lxml import etree

monkey.patch_all()

domain = "quanxue.cn"

exp_url = set()

defeated_url = []


def requ(url):
    jobs = []
    if domain in url:
        if url in exp_url:
            return
        else:
            exp_url.add(url)
        print("GET:%s" % url)
        try:
            req = requests.get(url)
            data = req.content
            select = etree.HTML(data)
            links = select.xpath("//a/@href")
            for link in links:
                if 'http://' not in link:
                    link = url[:url.rindex('/') + 1] + link
                    jobs.append(gevent.spawn(requ, link))
                else:
                    jobs.append(gevent.spawn(requ, link))
                    gevent.joinall(jobs)
                printlen(exp_url)


34         except Exception, e:
35
print
"ERROR"
36
defeated_url.append(url)
37
38
39 if __name__ == ‘__main__‘:
40
try:
    41
    url = "http://www.quanxue.cn"
42
requ(url)
43     except:
44
print
exp_url
45
print
defeated_url
46     finally:
47
print
defeated_url
48
print
exp_url
