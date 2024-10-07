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
