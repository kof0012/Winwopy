# -*- coding: utf-8 -*-
import scrapy
import re
import json
import time
from urllib import parse
from scrapy.loader import ItemLoader
from ArticleSpider.items import ZhihuAnswerItem, ZhihuQuestionItem
import datetime


class ZhihuSpider(scrapy.Spider):
    name = 'zhihu'
    allowed_domains = ['www.zhihu.com']
    start_urls = ['https://www.zhihu.com/']
    start_answer_url = 'https://www.zhihu.com/api/v4/questions/{}/answers?sort_by=default&include=data%5B%2A%5D.is_normal%2Cadmin_closed_comment%2Creward_info%2Cis_collapsed%2Cannotation_action%2Cannotation_detail%2Ccollapse_reason%2Cis_sticky%2Ccollapsed_by%2Csuggest_edit%2Ccomment_count%2Ccan_comment%2Ccontent%2Ceditable_content%2Cvoteup_count%2Creshipment_settings%2Ccomment_permission%2Ccreated_time%2Cupdated_time%2Creview_info%2Cquestion%2Cexcerpt%2Crelationship.is_authorized%2Cis_author%2Cvoting%2Cis_thanked%2Cis_nothelp%2Cupvoted_followees%3Bdata%5B%2A%5D.mark_infos%5B%2A%5D.url%3Bdata%5B%2A%5D.author.follower_count%2Cbadge%5B%3F%28type%3Dbest_answerer%29%5D.topics&limit=20&offset=0'

    headers = {
        'HOST': 'www.zhihu.com',
        'Referer': 'https://www.zhihu.com',
        'User-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8'
    }

    def parse(self, response):
        all_urls = response.xpath('//@href').extract()
        all_urls = [parse.urljoin(response.url, url) for url in all_urls]
        all_urls = filter(lambda x: True if re.match(r'.*zhihu.com/question', x) else False, all_urls)
        for url in all_urls:
            match_obj = re.match(r'(.*zhihu.com/question/(\d+))', url)
            if match_obj:
                request_url = match_obj.group(1)
                zhihu_id = match_obj.group(2)
                yield scrapy.Request(request_url, headers=self.headers, callback=self.parse_question,
                                     meta={'zhihu_id': zhihu_id})
            else:
                yield scrapy.Request(url, headers=self.headers, callback=self.parse)

    def parse_question(self, response):
        item_loader = ItemLoader(item=ZhihuQuestionItem(), response=response)
        item_loader.add_value('zhihu_id', response.meta.get('zhihu_id', {}))
        item_loader.add_xpath('topics', '//div[@class="QuestionHeader-topics"]/div//text()')
        item_loader.add_value('url', response.url)
        item_loader.add_xpath('title', '//h1[@class="QuestionHeader-title"]/text()')
        item_loader.add_css("content", ".QuestionHeader-detail")
        item_loader.add_xpath('answer_num', '//h4[@class="List-headerText"]//text()')
        item_loader.add_xpath('comments_num', '//div[@class="QuestionHeader-Comment"]/button[1]//text()')
        item_loader.add_value('watch_user_num', response.xpath('//div[@class="NumberBoard-value"]/text()').extract()[0])
        item_loader.add_value('click_num', response.xpath('//div[@class="NumberBoard-value"]/text()').extract()[1])

        question_item = item_loader.load_item()

        yield scrapy.Request(self.start_answer_url.format(response.meta.get('zhihu_id'), {}), headers=self.headers,
                             callback=self.parse_answer)
        yield question_item

    def parse_answer(self, response):
        ans_json = json.loads(response.text)
        is_end = ans_json['paging']['is_end']
        next_url = ans_json['paging']['next']

        for answer in ans_json['data']:
            answer_item = ZhihuAnswerItem()
            answer_item['zhihu_id'] = answer['id']
            answer_item['url'] = answer['url']
            answer_item['question_id'] = answer['question']['id']
            answer_item['author_id'] = answer['id']
            answer_item['content'] = answer['content'] if 'content' in answer else None
            answer_item['praise_num'] = answer['voteup_count']
            answer_item['comments_num'] = answer['comment_count']
            answer_item["create_time"] = answer["created_time"]
            answer_item['update_time'] = answer['question'].get('updated_time', None)
            answer_item["crawl_time"] = datetime.datetime.now()

            yield answer_item
        if not is_end:
            yield scrapy.Request(next_url, headers=self.headers, callback=self.parse_answer)
        pass

    def start_requests(self):
        return [scrapy.Request('https://www.zhihu.com/#signin', headers=self.headers, callback=self.log_in)]

    def log_in(self, response):
        match_obj = re.match(r'.*name="_xsrf" value="(.*?)"', response.text, re.S)
        if match_obj:
            xsrf = match_obj.group(1)
        if xsrf:
            post_data = {
                'captcha_type': 'cn',
                '_xsrf': xsrf,
                'email': 'fenhong.wang@163.com',
                'password': 'dickdick911',
                'captcha': '',
            }
        captcha_ur = 'https://www.zhihu.com/captcha.gif?r=%d&type=login&lang=cn' % (int(time.time() * 1000))
        return scrapy.Request(captcha_ur, headers=self.headers, meta={'post_data': post_data}, callback=self.log_after)

    def log_after(self, response):
        with open('captcha.gif', 'wb') as f:
            f.write(response.body)
            f.close()
        from PIL import Image
        try:
            img = Image.open('captcha.gif')
            img.show()
        except:
            pass
        seq = input('输入倒立字的位置')
        captcha = {
            'img_size': [200, 44],
            'input_points': [],
        }
        points = [[22.796875, 22], [42.796875, 22], [63.796875, 21], [84.796875, 20], [107.796875, 20],
                  [129.796875, 22], [150.796875, 22]]
        for i in seq:
            captcha['input_points'].append(points[int(i) - 1])
        captcha = json.dumps(captcha)

        post_url = 'https://www.zhihu.com/login/email'
        post_data = response.meta.get('post_data', {})
        post_data['captcha'] = captcha
        # 在这里完成像之前的requests的登录操作，每一个Request如果要做下一步处理都要设置callback
        return scrapy.FormRequest(
            url=post_url,
            formdata=post_data,
            headers=self.headers,
            callback=self.check_login
        )

    def check_login(self, response):
        # 验证服务器的返回数据判断是否成功
        text_json = json.loads(response.text)
        if 'msg' in text_json and text_json['msg'] == '登录成功':
            print('登录成功！')
            for url in self.start_urls:
                yield scrapy.Request(url, headers=self.headers, dont_filter=True)
        else:
            print('登陆失败', response.text)
