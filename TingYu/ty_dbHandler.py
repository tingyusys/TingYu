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
