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
