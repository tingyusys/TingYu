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
