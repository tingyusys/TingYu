<img src="https://socialify.git.ci/tingyusys/TingYu/image?description=1&descriptionEditable=%E5%9F%BA%E4%BA%8E%20aiohttp%20%E7%9A%84%E5%BC%82%E6%AD%A5%E8%AF%B7%E6%B1%82%E6%A1%86%E6%9E%B6&font=Inter&forks=1&issues=1&logo=https%3A%2F%2Fi-blog.csdnimg.cn%2Fdirect%2Fcb52a989c4d74c989e2142fdcbe5783b.jpeg&name=1&pattern=Circuit%20Board&pulls=1&stargazers=1&theme=Dark" alt="TingYu" width="640" height="320" style="zoom: 200%;" />

> 师傅们好，我是听雨落鱼，最近整合了我以前所有的爬虫脚本，尝试设计一个自己的框架，虽然现在很菜，但希望随着自己的学习，逐步更新，伴随他成长。（框架使用python11开发）

```plain
aiofiles
aiohttp
lxml
playwright
```



## 1、基础架构
### 1）文件结构输出脚本
```python
# -*- coding: utf-8 -*-
import os

def generate_tree(dir_path, prefix=""):
    # 获取指定目录下的所有文件和文件夹
    contents = os.listdir(dir_path)
    # 过滤掉隐藏文件和 __pycache__ 目录
    contents = [c for c in contents if not c.startswith('.') and c != '__pycache__']
    # 按照文件夹优先排序
    contents.sort(key=lambda x: (os.path.isfile(os.path.join(dir_path, x)), x))
    pointers = ['├── '] * (len(contents) - 1) + ['└── ']
    
    for pointer, content in zip(pointers, contents):
        path = os.path.join(dir_path, content)
        if os.path.isdir(path):
            print(prefix + pointer + content + "/")
            # 递归调用，进入子目录
            generate_tree(path, prefix + "│   ")
        else:
            print(prefix + pointer + content)

# 指定根目录为当前运行目录
root_dir = os.getcwd()
print(f"Root directory: {os.path.basename(root_dir)}/")
generate_tree(root_dir)

```

### 2）项目结构
```bash
Root directory: 异步框架尝试/
├── TingYu/
│   ├── __init__.py
│   ├── ty_dbHandler.py  # 负责处理数据
│   ├── ty_pipeline.py   # 爬取数据的出口
│   ├── ty_request.py    # 请求拦截器：拦截所有发出的数据包
│   ├── ty_response.py   # 响应拦截器：拦截所有发出的数据包
│   ├── ty_scheduler.py  # 管道：用于创建异步队列
│   └── ty_spider.py     # 爬虫类：用于编写正则
```

## 2、源码
### 1）__init__.py
```python
# -*- coding: utf-8 -*-

from .ty_scheduler import Scheduler
from .ty_request import Request
from .ty_response import Response
from .ty_spider import Spider
from .ty_pipeline import Pipeline, SaveDataType
from .ty_dbHandler import DBHandler

__all__ = [
    'Scheduler',
    'Request',
    'Response',
    'Spider',
    'Pipeline',
    "SaveDataType",
    "DBHandler",
]

```

### 2）ty_dbHandler.py
```python
# -*- coding: utf-8 -*-
import aiofiles
import asyncio


class DBHandler:
    def __init__(self, use_type=None, use_pipe_class=None):
        self.use_type = use_type
        self.db_list = []
        if use_type == "write" and use_pipe_class:
            self.use_pipe = use_pipe_class.send_file_scheduler
            self.field_list = use_pipe_class.field_list
        elif use_type == "write" and not use_pipe_class:
            raise ValueError("DBHandler ---》use_pipe_class 未传入")
        else:
            self.use_pipe = None

    async def parse(self, result_data):
        return result_data

    async def getTxtToDbListConcurrency(self, file):
        while True:
            line = await file.readline()
            if not line:  # 如果没有读取到内容，跳出循环
                break
            result_parse = await self.parse(line.strip())
            if not result_parse:
                continue
            if isinstance(result_parse, list):
                for i in result_parse:
                    self.db_list.append(i)
            elif isinstance(result_parse, dict):
                self.db_list.append(result_parse)  # 去掉首尾空白字符并添加到列表
            await asyncio.sleep(0.1)  # 可选：添加延迟以避免过高的CPU使用率

    async def getTxtToDbList(self, file_path, concurrency=5):
        """
        从 txt 文件里获取列表
        :param file_path: 文件路径
        :param concurrency: 并发数
        :return:
        """
        tasks = []
        async with aiofiles.open(file_path, mode='r') as file:
            # 启动多个 read_file 协程
            for _ in range(concurrency):
                tasks.append(self.getTxtToDbListConcurrency(file))
            await asyncio.gather(*tasks)  # 等待所有任务完成
            return list({frozenset(d.items()): d for d in self.db_list}.values())

    async def setPipelineToFileConcurrency(self, file):
        if not self.use_pipe:  # 没有实例化---》默认不运行
            return
        while True:
            try:
                pip_data = await asyncio.wait_for(
                    self.use_pipe.get_request(), timeout=10
                )
                if not pip_data:  # 管道数据为空，结束
                    break
                result_parse = await self.parse(pip_data)
                await file.write(str(result_parse))
            except asyncio.TimeoutError:  # 未知原因卡死---》退出
                break

    async def setPipelineToFile(self, file_path, concurrency=5):
        """
        把管道里的数据送到文件里
        :param file_path: 文件路径
        :param concurrency: 并发数
        :return:
        """
        tasks = []
        async with aiofiles.open(file_path, mode='a') as file:
            await file.write(','.join(self.field_list) + '\n')
            # 启动多个 read_file 协程
            for _ in range(concurrency):
                tasks.append(self.setPipelineToFileConcurrency(file))
            await asyncio.gather(*tasks)  # 等待所有任务完成

    def choose_db(self, *args, **kwargs):
        if not self.use_type:
            return
        if self.use_type == "read":
            return asyncio.run(self.getTxtToDbList(*args, **kwargs))
        if self.use_type == "write":
            return asyncio.run(self.setPipelineToFile(*args, **kwargs))

    async def async_choose_db(self, *args, **kwargs):
        if self.use_type == "write":
            await self.setPipelineToFile(*args, **kwargs)

```

### 3）ty_pipeline.py
```python
# -*- coding: utf-8 -*-
# tingyu/pipeline.py
import asyncio

from .ty_scheduler import Scheduler
from .ty_dbHandler import DBHandler


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


class SaveDataType:
    NEXT_SPIDER = "send_next_spider"
    CSV = "save_csv"
    PRINT = "save_print"


class Pipeline:
    def __init__(self, spider_class):
        self.process_type = spider_class.save_data_type or SaveDataType.PRINT
        # 数据管道
        self.data_scheduler = spider_class.data_scheduler
        # 根据管道类型选择管道方法
        self.choose_pipeline_dict = {
            SaveDataType.PRINT: self.save_print,
            SaveDataType.NEXT_SPIDER: self.send_next_spider,
            SaveDataType.CSV: self.save_csv
        }
        self.next_spider_data_list = []
        self.file_path = spider_class.file_path
        self.send_file_scheduler = spider_class.send_file_scheduler
        self.field_list = spider_class.field_list

    async def start_pipeline(self):
        """
        运行管道--- 》 已有并发条件
        :return:
        """
        while True:
            try:
                result_data = await asyncio.wait_for(
                    self.data_scheduler.get_request(), timeout=2
                )
                if not result_data:
                    await self.send_file_scheduler.add_request(None)  # 你可能不用，但不影响正常关闭他
                    break
                # 检查是否有字段是列表
                if any(isinstance(value, list) for value in result_data.values()):
                    # 获取列表字段的长度
                    list_length = next(len(value) for value in result_data.values() if isinstance(value, list))
                    # 展开字典
                    for i in range(list_length):
                        new_dict = {key: (value[i] if isinstance(value, list) else value) for key, value in
                                    result_data.items()}
                        print("[+] 管道接收---> ", new_dict)
                        await self.choose_pipeline_dict.get(self.process_type)(new_dict)
                else:
                    print("[+] 管道接收---> ", result_data)
                    # print(f"----类型---》{self.process_type}")
                    await self.choose_pipeline_dict.get(self.process_type)(result_data)
            except asyncio.TimeoutError:
                await self.send_file_scheduler.add_request(None)
                break

    async def send_next_spider(self, result_data):
        """
        self.next_spider_data_list = [
            {
                "get_url": "xxx",
                "name": "张三"
            },
            {
                "get_url": "xxx",
                "name": "李四"
            },
        ]
        :return:
        """
        self.next_spider_data_list.append(result_data)

    async def save_print(self, result_data):
        print("管道拿到数据", result_data)

    async def save_csv(self, result_data):
        await self.send_file_scheduler.add_request(result_data)

    def save_txt(self):
        pass

    def save_db(self):
        pass

```

### 4）ty_request.py
```python
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

```

### 5）ty_response.py
```python
# -*- coding: utf-8 -*-
import json


class Response:
    def __init__(self, content, status, content_length, headers=None, cookies=None, url=None):
        self.content = self.decrypt(content)  # 响应内容
        self.status = status  # HTTP 状态码
        self.response_length = content_length
        self.headers = headers  # 响应头
        self.cookies = cookies  # 响应的 cookies
        self.url = url  # 最终请求的 URL

    def json(self):
        """尝试将响应内容解析为 JSON"""
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return None

    def decrypt(self, content):
        """
        解密函数---》默认不解密
        :return:
        """
        decrypt_data = content
        return decrypt_data

```

### 6）ty_scheduler.py
```python
# -*- coding: utf-8 -*-
"""
调度器
"""

import asyncio


class Scheduler:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def add_request(self, request):
        """将请求添加到队列中"""
        await self.queue.put(request)

    async def get_request(self):
        """从队列中获取请求"""
        return await self.queue.get()

    async def run(self):
        """运行调度器并处理请求队列中的请求"""
        while not self.queue.empty():
            request = await self.get_request()
            if request is None:
                break
            await request.fetch()

```

### 7）ty_spider.py
```python
# -*- coding: utf-8 -*-
# tingyu/spider.py
import asyncio
from playwright.async_api import async_playwright
from urllib.parse import urlparse

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
                tasks.append(CSVDBHandler(use_type="write", use_pipe_class=self).async_choose_db(self.file_path, self.concurrency))
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

```

## 3、框架使用
### 1）输入 URL
#### 【1】请求单个 url
```python
# -*- coding: utf-8 -*-

from TingYu import Spider

if __name__ == '__main__':
    url = "https://www.baidu.com"
    test = Spider(
        start_urls=url
    )
    test.run()
```

#### 【2】请求 url 列表
```python
# -*- coding: utf-8 -*-

from TingYu import Spider

if __name__ == '__main__':
    url_list = [
        "https://www.baidu.com/1",
        "https://www.baidu.com/2",
        "https://www.baidu.com/3",
        "https://www.baidu.com/4"
   ]
    test = Spider(
        start_urls=url_list
    )
    test.run()
```

#### 【3】请求 txt 文件
```python
# -*- coding: utf-8 -*-

from TingYu import Spider

if __name__ == '__main__':
    url_txt_path = "url.txt"
    test = Spider(
        start_urls=url_list
    )
    test.run()
```

**txt 文件里面可放置：域名-ip-url**

```bash
https://www.baidu.com/1
135.23.6.3
135.23.6.898:9999
www.baidu.com
```

### 2）控制并发
```python
# -*- coding: utf-8 -*-

from TingYu import Spider

if __name__ == '__main__':
    url = "https://www.baidu.com"
    test = Spider(
        start_urls=[url] * 10,
        concurrency=10  # 通过这个参数来控制并发的数量
    )
    test.run()

```

### 3）自定义爬虫规则
> 在不同的爬虫项目里，往往有不同的规则，可以自定义来适配不同的项目
>

#### 【1】基础使用
+ 需要写一个类 ---》继承 Spider
+ 然后重新异步方法 parse
+ 在异步方法 parse ---》编写自定义匹配规则---》xpath + re + json ---》通过 response 参数拿到数据

```python
# -*- coding: utf-8 -*-

from TingYu import Spider


class MySpider(Spider):
    async def parse(self, response):
        print(response.url)
        print(response.status)
        print(response.headers)
        print(response.cookies)
        print(response.content)
        print(response.json())


if __name__ == '__main__':
    url = "https://www.baidu.com"
    test = MySpider(
        start_urls=[url] * 10,
        concurrency=10
    )
    test.run()

```

### 4）处理请求
#### 【1】配置代理
```python
# -*- coding: utf-8 -*-

from TingYu import Spider, Request, Scheduler
import asyncio

# 自己的请求类
class MyRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy = "http://127.0.0.1:8080"  # 配置代理

# 自己的爬虫类
class MySpider(Spider):
    async def parse(self, response):
        print(response.status, response.content)
        return None

if __name__ == '__main__':
    api_url = 'https://jsonplaceholder.typicode.com/posts/1'
    baidu_url = "https://b.bdstatic.com/searchbox/image/gcp/20230628/523194697.json"
    myspider = MySpider(
        start_urls=baidu_url,
        request_class=MyRequest,  # 把自己的请求类送到里面
        concurrency=4
    )
    myspider.run()
```

#### 【2】发送 get 请求（默认）
```python
# -*- coding: utf-8 -*-

from TingYu import Spider, Request


class MyRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method = 'GET'
        # get 请求携带固定参数 ---》http://www.baidu.com?q=123
        self.data = {
            "q": "123"
        }


if __name__ == '__main__':
    Spider(
        start_urls=['http://www.baidu.com'],
        request_class=MyRequest,
        use_playwright=False,
    ).run()

```

#### 【3】发送 post 请求（使用 json 构造数据）
```python
# -*- coding: utf-8 -*-

from TingYu import Spider, Request


class MyRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method = 'POST'
        # POST 请求携带固定参数，json 构造数据
        self.json = {
            "q": "123"
        }


if __name__ == '__main__':
    Spider(
        start_urls=['http://www.baidu.com'],
        request_class=MyRequest,
        use_playwright=False,
    ).run()
```

```http
POST /web/122 HTTP/1.1
Host: xxx.com
Content-Length: 564
sw_need_sign: true
Accept: application/json
Content-Type: application/json
Cookie: _sw_envid=sdgfsdgfsdgsdf
Connection: close

{
    "q": "123"
}
```

#### 【4】发送 post 请求（使用 data 构造数据）
```python
# -*- coding: utf-8 -*-

from TingYu import Spider, Request


class MyRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method = 'POST'
        self.proxy = "http://127.0.0.1:8080"
        self.data = {
            "q": "123",
            "w": "asdf"
        }


if __name__ == '__main__':
    Spider(
        start_urls="http://192.168.8.106:1130",
        request_class=MyRequest,
        concurrency=3
    ).run()

```

```python
POST / HTTP/1.1
Host: 192.168.8.106:1130
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br
Referer: https://www.google.com
Connection: close
Accept: */*
Content-Length: 12
Content-Type: application/x-www-form-urlencoded

q=123&w=asdf
```

#### 【5】发送动态参数
```python
# -*- coding: utf-8 -*-

from TingYu import Spider, Request


class MyRequest(Request):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.method = 'POST'
        self.proxy = "http://127.0.0.1:8080"
        # 使用 data 或者 json 配置不变的参数
        self.data = {
            "q": "123",
            "w": "asdf"
        }
        # 这个可以是从txt文件或者其他文件里拿到的测试列表
        # 列表里面构造的数据，就是多种多样的了 [{"sql注入poc":"and 1=1--+"}]
        self.poc_list = [i for i in range(100)]

    async def encryption(self, data, poc):
        # 配置：例如时间戳---》这个变化的参数
        # 可以直接生成，也可以选择使用poc列表里面的值
        data["sign"] = poc
        print("运送poc：", data)
        return data


if __name__ == '__main__':
    Spider(
        start_urls="http://192.168.8.106:1130",
        request_class=MyRequest,
        concurrency=3
    ).run()

```

#### 【6】进行 js 逆向的参数加密
pass





### 5）处理响应
#### 【1】进行 js 逆向的参数解密
pass



### 6）递归爬虫
+ 上一级重新的爬虫类---》通过 get_url 字段---》返回要请求的url
+ save_data_type参数---》设置为 SaveDataType.NEXT_SPIDER
+ 将 run 函数返回的结果，作为二级爬虫的 start_urls 参数传进去

```python
# -*- coding: utf-8 -*-

from TingYu import Spider, SaveDataType


class OneSpider(Spider):
    async def parse(self, response):
        # 假设这个是通过 正则或者xpath 拿到的 url
        url = "http://192.168.8.106:1130"
        # 也可以是url列表
        url_list = [url] * 10
        return {
            "get_url": url  # 给get_url字段，传入url或者url列表
        }


class TwoSpider(Spider):
    async def parse(self, response):
        print("处理第二层 url :", response.url)


if __name__ == '__main__':
    one_result = OneSpider(
        start_urls="http://192.168.8.106:1130",
        concurrency=3,
        save_data_type=SaveDataType.NEXT_SPIDER
    ).run()

    TwoSpider(
        start_urls=one_result,
        concurrency=3
    ).run()

```

### 7）保存数据
#### 【1】保存csv
+ save_data_type 参数---》设置为 SaveDataType.CSV
+ 填写 file_path 参数---》保存的文件路径 "test.csv"
+ 填写 field_list 参数---》字段列表 ["url", "status"]
+ 重写的爬虫类的 parse 函数，必须按照字段列表返回数据

```python
# -*- coding: utf-8 -*-
import time

from TingYu import Spider, SaveDataType

num = 0


class TestSpider(Spider):

    async def parse(self, response):
        global num
        num += 1
        data = {
            "url": response.url + " --- " + str(num),
            "status": response.status
        }
        # print(data)
        return data


# 测试并发 - 10086 - 500并发 ---》130.92 秒 --- 7230个数据 --- 丢包 3000个 延时 0.1 秒
# 测试并发 - 10086 - 500并发 ---》95.27 秒 --- 7159个数据 --- 丢包 3000个 延时 1 秒

# 测试并发 - 10086 - 100并发 ---》218.79 秒 --- 9499个数据 --- 丢包 587个 延时 0.1 秒
# 测试并发 - 10086 - 100并发 ---》249.01 秒 --- 10000个数据 --- 丢包 86个 延时 1 秒
# 性能调优                       209.58 秒     10018

if __name__ == '__main__':
    start_time = time.time()  # 记录开始时间

    TestSpider(
        start_urls=[f'https://jsonplaceholder.typicode.com/posts/{i}' for i in range(1000)],
        concurrency=300,
        save_data_type=SaveDataType.CSV,
        file_path="test.csv",
        field_list=["url", "status"]
    ).run()

    end_time = time.time()  # 记录结束时间
    elapsed_time = end_time - start_time  # 计算耗时
    print(f"程序运行时间: {elapsed_time:.2f} 秒")

```



## 4、框架案例
