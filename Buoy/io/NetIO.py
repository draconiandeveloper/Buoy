import html.parser
import aiohttp
import asyncio
import json
import sys
import os

class MLStripper(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()

        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_data(self):
        return ''.join(self.text)
    
    def strip_tags(self, html):
        self.feed(html)
        return self.get_data()
    
class NetIO:
    def __init__(self, url, headers={}, data=b''):
        self.url = url
        self.headers = headers
        self.data = data
    
    async def _get_response(self, method='GET'):
        _method = f'session.{method.lower()}'
        async with aiohttp.ClientSession() as session:
            return eval(_method)(self.url, headers=self.headers, data=self.data)
    
    async def _get_text(self):
        async with self._get_response() as response:
            return await response.text()
    
    async def _get_json(self):
        async with self._get_response() as response:
            return await json.loads(response.json())

    async def _post_json(self):
        async with self._get_response('POST') as response:
            return await response.text()
    
    def get_text(self):
        return asyncio.run(self._get_text())
    
    def get_json(self):
        return asyncio.run(self._get_json())
    
    def post_json(self):
        return asyncio.run(self._post_json())