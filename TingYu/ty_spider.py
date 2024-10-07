# -*- coding: utf-8 -*-
# tingyu/spider.py
import asyncio
from playwright.async_api import async_playwright
from urllib.parse import urlparse
from lxml import etree

from .ty_request import Request
from .ty_pipeline import Pipeline, SaveDataType
from .ty_scheduler import Scheduler
from .ty_dbHandler import DBHandler


class UrlDBHandler(DBHandler):
    async def parse(self, result_data):
        if "." not in result_data:
            raise ValueError("文件里不是 url-域名-ip ：", result_data)
        if urlparse(result_data).scheme in ['http', 'https']:
            return {"get_url": result_data}

            # 处理域名或id+port形式
        if ':' in result_data:
            # 分割ID和端口号
            id_part, port_part = result_data.split(':', 1)
        else:
            id_part = result_data
            port_part = None
        # 构造HTTP和HTTPS URL
        http_url = f'http://{id_part}'
        https_url = f'https://{id_part}'
        if port_part:
            http_url += f':{port_part}'
            https_url += f':{port_part}'
        return [{"get_url": http_url}, {"get_url": https_url}]


class CSVDBHandler(DBHandler):
    async def parse(self, result_data):
        """
        传入 ---》{"xx":123, "qq": "asdf"}
        :param result_data:
        :return:
        """
        new_result_data = {}
        for i in self.field_list:
            new_result_data[i] = result_data.get(i)
        return ",".join(map(str, new_result_data.values())) + "\n"


class Spider:
    def __init__(self,
                 start_urls=None,
                 concurrency=100,
                 use_playwright=False,
                 request_class=None,
                 pipeline_class=None,
                 save_data_type=None,
                 file_path=None,
                 field_list=None
                 ):
        """
        初始化爬虫类
        :param start_urls: 请求的url---》str | list | “xxx.txt” | 上一个Spider类运行的结果
        :param concurrency: 并发数
        :param use_playwright: 是否启用浏览器
        :param request_class: 处理请求的类
        :param pipeline_class: 管道类
        :param save_data_type: 保存数据的类型
        :param file_path: 保存的文件路径
        :param field_list: 字段列表
        """

        self.use_playwright = use_playwright  # 是否使用 Playwright 绕过无头浏览器检测
        self.concurrency = concurrency  # 控制并发数
        self.start_urls = self.data_init(start_urls)

        self.url_scheduler = Scheduler()  # url 调度器--->队列
        self.data_scheduler = Scheduler()  # 数据调度器--->队列
        self.send_file_scheduler = Scheduler()  # 数据写入文件的调度器--->队列

        self.file_path = file_path  # 文件路径---》pipe 使用
        self.save_data_type = save_data_type  # 使用的管道类别---》pipe 使用
        self.field_list = field_list  # 保存的字段名---》pipe 使用

        self.ty_request_class = (request_class or Request)(self)  # 如果用户没有提供，使用默认 Request 类
        self.ty_pipeline_class = (pipeline_class or Pipeline)(self)  # 实例化管道---》数据处理

    def data_init(self, start_urls):
        if not start_urls:  # 默认访问百度
            return [{"get_url": "https://www.baidu.com"}]
        if isinstance(start_urls, str):
            if ".txt" in start_urls:  # 传入 url txt文件
                print(f"正在读取{start_urls}文件。。。")
                return UrlDBHandler(use_type="read").choose_db(file_path=start_urls, concurrency=self.concurrency)
            return [{"get_url": start_urls}]
        if isinstance(start_urls, list) and isinstance(start_urls[0], str):
            return [{"get_url": url} for url in start_urls]
        if isinstance(start_urls, list) and isinstance(start_urls[0], dict):
            return start_urls  # 能走到这里，说明是上一个爬虫类传过来的
        raise ValueError('你传递的数据结构不正确---》请传递字符串、列表或者 [{"get_url": "https://www.baidu.com"}]')

    async def parse(self, response):
        """
        默认解析方法
        response ---> 响应类
        必须返回一个字典---》如果想继续爬取字段---》返回的字典里必须有 get_url 字段
        """
        print(f"请求的url: \n{response.content}")
        return None

    def create_xpath(self, response):
        return etree.HTML(response.content)

    async def aiohttp_requests_producer(self, ):
        for url_dict in self.start_urls:
            await self.url_scheduler.add_request(url_dict)
        for _ in range(self.concurrency):
            await self.url_scheduler.add_request(None)

    async def start_requests(self):
        """生成初始请求"""
        tasks = []
        if self.use_playwright:
            async with async_playwright() as p:
                # 只打开一次浏览器
                browser = await p.chromium.launch(headless=False)  # 使用有头模式

                # 创建一个信号量，限制同时打开的页面数量
                sem = asyncio.Semaphore(self.concurrency)

                async def sem_task(task):
                    async with sem:  # 限制并发页面数量
                        return await task

                # 创建任务，复用同一个浏览器实例，并限制页面并发数
                tasks = [
                    sem_task(self.ty_request_class(url, self.parse).playwright_request(browser))
                    for url in self.start_urls
                ]

                # 并行执行所有任务
                await asyncio.gather(*tasks)

                # 在所有任务完成后关闭浏览器
                await browser.close()
        else:
            # 使用 aiohttp 生成任务
            tasks.append(self.aiohttp_requests_producer())
            # 开启 csv 文件写入
            if self.save_data_type == SaveDataType.CSV:
                tasks.append(CSVDBHandler(use_type="write", use_pipe_class=self).async_choose_db(self.file_path,
                                                                                                 self.concurrency))
            for _ in range(self.concurrency):  # 并发数
                tasks.append(self.ty_request_class.fetch())  # 开始爬虫任务
                tasks.append(self.ty_pipeline_class.start_pipeline())  # 开始数据处理
            await asyncio.gather(*tasks)

    async def crawl(self):
        """启动爬虫并根据用户的并发数设置任务调度"""
        # 获取请求任务
        await self.start_requests()
        return self.ty_pipeline_class.next_spider_data_list

    def run(self):
        return asyncio.run(self.crawl())
