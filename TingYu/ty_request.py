# -*- coding: utf-8 -*-
import asyncio
import random
import aiohttp
from playwright.async_api import async_playwright

from .ty_response import Response

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
    # 可以加入更多 User-Agent 以供随机选择
]


class Request:
    def __init__(self, spider_class, method='GET', headers=None, data=None, json=None, proxy=None):
        self.callback = spider_class.parse
        self.method = method
        self.headers = headers or self.default_headers()
        self.data = data
        self.json = json
        self.proxy = proxy  # 增加 proxy 参数支持
        self.ty_response_class = Response  # 响应类

        self.url_scheduler = spider_class.url_scheduler
        self.data_scheduler = spider_class.data_scheduler

        self.poc_list = ["tingyu1"]

    async def encryption(self, data, poc):
        """
        加密函数
        默认不加密
        :return:
        """
        encryption_data = data
        return encryption_data

    async def send_request(self, res_data, poc, session, url):

        requests_params_type = None
        if self.method == 'GET':
            requests_params_type = await self.encryption(self.data, poc)
            requests_data_type = None
            requests_json_type = None
        elif self.data:
            requests_data = await self.encryption(self.data, poc)
            requests_data_type = requests_data
            requests_json_type = None
        else:
            requests_data = await self.encryption(self.json, poc)
            requests_data_type = None
            requests_json_type = requests_data
        # print("请求的url", url)
        await asyncio.sleep(1)
        async with session.request(self.method, url, headers=self.headers, data=requests_data_type,
                                   json=requests_json_type,
                                   params=requests_params_type,
                                   ssl=False,
                                   proxy=self.proxy) as response:

            content_length = response.content_length  # 获取响应包的长度
            content = await response.text()  # 获取网站返回内容
            # 把获取到的网站返回内容封装为 Response 类，并传入回调函数中
            resp = self.ty_response_class(content, response.status, content_length, url=url)
            result = await self.callback(resp)  # 获取正则修改的数据

            if not result:  # 如果没有返回数据---》不要往数据队列添加数据
                return
            if not isinstance(result, dict):
                raise TypeError(f"spider ---> parse函数 : 应该返回字典 || {result}")
            # print("拿到数据", result)
            # 新老数据合并  ---》 {old} + {new}
            res_data.update(result)
            await self.data_scheduler.add_request(res_data)

    async def fetch(self):
        """
        aiohttp 方式发起请求
        传入---》json 将请求的 Content-Type 头部设置为 application/json
        传入---》data 将请求的 Content-Type 头部设置为 application/x-www-form-urlencoded
        """
        while True:  # 第一层死循环是为了获取 url
            try:
                res_data = await asyncio.wait_for(
                    self.url_scheduler.get_request(), timeout=2
                )
                if not res_data:
                    await self.data_scheduler.add_request(None)
                    break
                url = res_data.get("get_url")  # 获取传入的 url
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    for poc in self.poc_list:
                        await self.send_request(res_data, poc, session, url)
            except asyncio.TimeoutError:
                await self.data_scheduler.add_request(None)
                break
            except aiohttp.ClientConnectorError:
                pass
            except Exception as f:
                await asyncio.sleep(1)
                print("报错：", f)

    async def playwright_request(self, browser):
        """使用 Playwright 生成请求"""
        page = await browser.new_page()  # 创建页面
        try:
            await page.goto(self.url)
            await page.wait_for_load_state('load')  # 等待页面加载完成
            await asyncio.sleep(1.5)
            content = await page.content()  # 获取页面内容
            status = 200  # 假设状态码
            # 创建响应对象并回调
            resp = self.ty_response_class(content, status, url=self.url)
            await self.callback(resp)
        except Exception as e:
            print(f"Error occurred while processing {self.url}: {str(e)}")
        finally:
            await page.close()  # 确保页面关闭

    def default_headers(self):
        """返回随机化的 User-Agent 以及伪装的其他请求头"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com',
            'Connection': 'keep-alive'
        }
