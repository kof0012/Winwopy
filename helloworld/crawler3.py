#!/usr/bin/python3
import re
import urllib.request
from queue import Queue
from threading import Thread

depth = 10000


class DownloadThread(Thread):
    '''多线程抓取'''

    def __init__(self, url, queue):
        Thread.__init__(self)
        self.url = url
        self.queue = queue

    def download(self, url):
        # 抓取mails结果并返回
        sites = []
        searched_sites = []
        sites.append(self.url)
        mails = set()
        while len(sites) > 0:
            site = sites.pop()
            user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
            headers = {'User-Agent': user_agent}
            try:
                req = urllib.request.Request(site, headers=headers)
                response = urllib.request.urlopen(req)
                html = response.read().decode("utf-8")
            except:
                html = ""
            i = html.find("</head>")
            if i > -1:
                html = html[i + 7:]
            mails.update(self.find_mails(html))
            current_links = self.find_sites(html)
            for i in current_links:
                if (i not in sites) and (i not in searched_sites) and len(searched_sites) < depth:
                    print("Found site: " + i)
                    sites.append(i)
                    searched_sites.append(i)
        print(mails)
        return mails

    def run(self):
        # 构造抓取线程run方法，将mails结果推进队列
        data = self.download(self.url)
        self.queue.put(data)

    def find_mails(self, string):
        # mails列表
        patt = r"( [-.\w]+?@[-.\w]+?\.\w+ |mailto:[-.\w]+?@[-.\w]+?\.\w+)"
        res = []
        for match in re.findall(patt, string, re.S):
            m = re.sub(r'\s|mailto:', '', match)

            if m.endswith(('.jpg', '.png', '.gif', '.pdf', '.jpeg', '.css', '.js', '.mp3', '.mp4', '.zip', '.mov',
                           '.cgi', '.asp', '.php', '.aspx', '.exe')):
                continue
            else:
                print("\t Found mail: " + m)
                res.append(m)
        return res

    def find_sites(self, string):
        # urls列表
        patt = r"( http://[-.\w]+?\.\w+? | https://[-.\w]+?\.\w+? | www\.[-.\w]+?\.\w+? |href=\"http://.*?\")"
        res = []
        for match in re.finditer(patt, string):
            m = match.group()
            m = m.replace(" ", "")
            m = m.replace("href=\"", "")
            m = m.replace("\"", "")

            not_allowed = False
            if m.endswith(('.jpg', '.png', '.gif', '.pdf', '.jpeg', '.css', '.js', '.mp3', '.mp4', '.zip', '.mov',
                           '.cgi', '.asp', '.php', '.aspx', '.exe')):
                not_allowed = True
            if not_allowed is False and m.find("=") == -1 and m.find("?") == -1:
                res.append(m)
        return res


class WriteThread(Thread):
    '''单线程将结果写入txt文档'''

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def write(self, data):
        with open('e-mail-crawler-master.txt', 'a') as f:
            for iq in data:
                f.write(iq + '\r\n')

    def run(self):
        # 构造线程run方法并调用wrire写入
        while True:
            data = self.queue.get()
            if data == -1:
                break
            self.write(data)


q = Queue()
dThreads = [DownloadThread(url, q) for url in ["https://www.yooli.com/static/contactus/", "http://www.sohu.com"]]
wThread = WriteThread(q)
for t in dThreads:
    t.start()
wThread.start()
for t in dThreads:
    t.join()  # 主线程等待结束
q.put(-1)  # 发送结束信号给writethread
