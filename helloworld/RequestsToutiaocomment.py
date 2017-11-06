import hashlib
import json
import time

import pymysql
import requests
from fake_useragent import UserAgent
from requests.exceptions import RequestException

ua = UserAgent()

conn = pymysql.Connect(host="127.0.0.1", port=3306,
                       user='root', passwd='root', db='spider', charset='utf8')
cursor = conn.cursor()


def getASCP():
    t = round(time.time())
    e = hex(t).upper()[2:]
    m = hashlib.md5()
    m.update(str(t).encode(encoding='utf-8'))
    i = m.hexdigest().upper()

    if len(e) != 8:
        AS = '479BB4B7254C150'
        CP = '7E0AC8874BB0985'
        return AS, CP

    n = i[0:5]
    a = i[-5:]
    s = ''
    r = ''
    for o in range(5):
        s += n[o] + e[o]
        r += e[o + 3] + a[o]

    AS = 'A1' + s + e[-3:]
    CP = e[0:3] + r + 'E1'
    return AS, CP


def start_requests(maxtime=0):
    AS, CP = getASCP()
    headers = {'User-Agent': ua.random}
    feed_url = 'https://www.toutiao.com/api/pc/feed/'
    payloads = {'max_behot_time': maxtime, 'category': '__all__', 'utm_source': 'toutiao', 'widen': 1,
                'tadrequire': 'false', 'as': AS, 'cp': CP}
    try:
        r = requests.get(feed_url, params=payloads, headers=headers).json()
        if 'data' in r.keys():
            return r
    except RequestException as e:
        print('请求不成功', e)
        return None


def parse_detail(response):
    for i in response.get('data', None):
        if i.get('is_feed_ad') == False:
            result = {'title': i.get('title'), 'tags': i.get('chinese_tag'), 'comments': i.get(
                'comments_count'), 'url': 'https://www.toutiao.com' + i.get('source_url')}
            print(result)
            insert_mysql(result)

    if response.get('next'):
        maxtime = response.get('next').get('max_behot_time')

        return parse_detail(start_requests(maxtime=maxtime))


def write_json(result):
    with open('tt.txt', 'a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')


def insert_mysql(result):
    try:

        sql_in = "insert into toutiaocomment(title,tags,comments,url) VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE comments=VALUES(comments)"
        cursor.execute(
            sql_in, (result['title'], result['tags'], result['comments'], result['url']))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()


def main():
    response = start_requests()
    parse_detail(response)


if __name__ == '__main__':
    main()
