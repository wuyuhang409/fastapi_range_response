import os
import random
import re
import hashlib
from urllib.parse import quote
from email.utils import formatdate
from abc import ABC, abstractmethod
from mimetypes import guess_type
from typing import Sequence, Tuple, Optional, Mapping, Union, AnyStr, Dict, Callable

from starlette import status as http_status
from starlette.background import BackgroundTask
from starlette.responses import Response
from starlette.types import Scope, Receive, Send

from fastapi_range_response.exceptions import *


class BaseRangeResponse(ABC, Response):
    """
    实现了基于starlette的RangeResponse基类

    http range protocol https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests
    """

    def __init__(self,
                 path: str,
                 *,
                 media_type: Optional[str] = None,
                 download_name: Optional[str] = None,
                 headers: Optional[Mapping[str, str]] = None,
                 background: Optional[BackgroundTask] = None,
                 chunk_size: int = 1024 * 256) -> None:
        super().__init__()
        self.path = path
        self.download_name = download_name
        self.media_type = media_type or guess_type(download_name or self.file_name)[0] or 'application/octet-stream'
        self.background = background
        self.chunk_size = chunk_size
        if not headers:
            headers = {}
        self.init_headers(headers)

    def common_headers(self, file_mtime: Union[float, int], file_size: int) -> Mapping[str, str]:
        headers: Dict[str, str] = {
            "accept-ranges": "bytes",
            "last-modified": formatdate(self.file_mtime, usegmt=True),
            "etag": f'"{self.generate_etag(file_mtime, file_size)}"',
        }
        if self.download_name or self.media_type == "application/octet-stream":
            download_name = self.download_name or self.file_name
            content_disposition = (
                "attachment; "
                f"filename*=utf-8''{quote(download_name)}"
            )
            headers["content-disposition"] = content_disposition
        return headers

    @property
    def file_name(self) -> str:
        return os.path.basename(self.path)

    @property
    @abstractmethod
    def file_mtime(self) -> Union[float, int]:
        ...

    @property
    @abstractmethod
    def file_size(self) -> int:
        ...

    def to_raw_headers(self, headers: Mapping[AnyStr, AnyStr]) -> Sequence[Tuple[bytes, bytes]]:
        raws = []
        for key, value in headers.items() if isinstance(headers, dict) else {}:
            if not isinstance(key, (str, bytes)) or not isinstance(value, (str, bytes)):
                raise TypeError(f'item(key: {key}, value: {value}) is not anyStr')
            if isinstance(key, str):
                key = key.encode('latin-1')
            if isinstance(value, str):
                value = value.encode('latin-1')
            raws.append((key, value))
        return raws

    def generate_etag(self, mtime: float, size: int) -> str:
        """根据文件更新时间/文件大小生成etag"""
        return hashlib.md5(f'{int(mtime)}-{size}'.encode()).hexdigest()

    def check_if_range(self, if_range_line: str, mtime: float, size: int) -> bool:
        """验证if-range与文件etag相同或与文件更新时间相同"""
        return if_range_line == self.generate_etag(mtime, size) or if_range_line == formatdate(mtime, usegmt=True)

    def parse_range(self, range_line: str, max_size: int) -> Sequence[Tuple[int, int]]:
        """
        格式化http range

        Args:
            range_line(str): http-range content
            max_size(int): file size

        Returns:
            返回一个序列, 每个序列为解析的多个range段
            [(0, 1024), (1024, 2048), ...]
        """
        try:
            unit, ranges_str = range_line.split("=", maxsplit=1)
        except ValueError:
            raise MalformedRangeHeaderError()
        if unit != "bytes":
            raise MalformedRangeHeaderError("Only support bytes range")
        ranges = []
        for start, end in re.findall(r"(\d*)-(\d*)", ranges_str):
            if start == '' and end == '':
                continue
            if end == '':
                end = self.file_size - 1
            start, end = int(start), int(end)
            if not (0 <= start < self.file_size):
                raise RangeNotSatisfiableError(self.file_size)
            if end >= self.file_size:
                end = self.file_size - 1
            if start > end:
                raise MalformedRangeHeaderError("Range header: start must be less than end")
            ranges.append((start, end))
        if len(ranges) == 0:
            raise MalformedRangeHeaderError("Range header: range must be requested")

        return ranges

    def parse_multiple_header(self, ranges: Sequence[Tuple[int, int]], boundary: str) -> Tuple[int, bytes, Callable[[int, int], bytes]]:
        """
        获取多块range的总长度及根据start, end, 生成sub header的函数

        约定处理multiple range时, response header需要设置Content-Type为 multipart/byteranges; boundary={13位随机数}

        正文部分使用两个--{boundary}来确定一块内容

        # 请求示例
        curl http://www.example.com -i -H "Range: bytes=0-50, 100-150"

        # response header
        HTTP/1.1 206 Partial Content
        Content-Type: multipart/byteranges; boundary=3d6b6a416f9b5
        Content-Length: 282

        # response body  response header与response body固定有一个空行
        --3d6b6a416f9b5
        Content-Type: text/html
        Content-Range: bytes 0-50/1270

        我是0-50部分的正文
        --3d6b6a416f9b5
        Content-Type: text/html
        Content-Range: bytes 100-150/1270

        我是100-150部分的正文
        --3d6b6a416f9b5--
        """

        def create_sub_header(l_start: int, l_end: int) -> bytes:
            return (f"Content-Type: {self.media_type}\n"
                    f"Content-Range: bytes {l_start}-{l_end}/{self.file_size}\n"
                    "\n").encode("latin-1")

        start_body = f'\n--{boundary}\n'.encode('latin-1')
        sum_size = 0
        sum_size += len(start_body)
        for start, end in ranges:
            sum_size += (len(create_sub_header(start, end))
                         + (end - start) + 1 + len('\n')
                         + len(f'--{boundary}\n'))

        return sum_size, start_body, create_sub_header

    def parse_chunks(self, start: int, end: int) -> Sequence[Tuple[int, int]]:
        chunks = []
        current_start = start
        while current_start < end:
            current_end = min(current_start + self.chunk_size, end)
            chunks.append((current_start, current_end))
            current_start += self.chunk_size
        return chunks

    async def setup(self):
        for key, value in self.common_headers(self.file_mtime, self.file_size).items():
            self.headers[key] = value

    @abstractmethod
    async def send_file(self, send: Send, path: str, start: int, end: int):
        """发送文件流, 注意, start, end为索引位, 如果索引为0, 100, 代表需要读取从0,1,2,3....100共计101个字节"""

    async def handle_all(self, send_header_only: bool, scope: Scope, send: Send):
        self.headers["content-range"] = f"bytes {0}-{self.file_size - 1}/{self.file_size}"
        self.headers['content-type'] = self.media_type
        self.headers['content-length'] = str(self.file_size)
        await send({
            'type': 'http.response.start',
            'status': http_status.HTTP_200_OK,
            'headers': self.headers.raw,
        })
        if send_header_only:
            return await send({'type': 'http.response.body', 'body': b''})
        await self.send_file(send, self.path, start=0, end=self.file_size - 1)
        return await send({
            'type': 'http.response.body',
            'body': b'',
        })

    async def handle_single_range(self, send_header_only: bool, scope: Scope, send: Send, start: int, end: int):
        self.headers["content-range"] = f"bytes {start}-{end}/{self.file_size}"
        self.headers["content-type"] = str(self.media_type)
        self.headers["content-length"] = str(end + 1 - start)
        if send_header_only:
            return await send({
                'type': 'http.response.body',
                'body': b''
            })

        await send({
            'type': 'http.response.start',
            'status': http_status.HTTP_206_PARTIAL_CONTENT,
            'headers': self.headers.raw
        })
        await self.send_file(send, self.path, start, end)
        return await send({
            'type': 'http.response.body',
            'body': b'',
        })

    async def handle_multiple_range(self, send_header_only: bool, scope: Scope, send: Send, ranges: Sequence[Tuple[int, int]]):
        boundary = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=13))
        content_length, start_body, create_sub_header = self.parse_multiple_header(ranges, boundary)
        self.headers['content-length'] = str(content_length)
        self.headers['content-type'] = f'multipart/byteranges; boundary={boundary}'
        await send({
            'type': 'http.response.start',
            'status': http_status.HTTP_206_PARTIAL_CONTENT,
            'headers': self.headers.raw
        })
        if send_header_only:
            return await send({
                'type': 'http.response.body',
                'body': b''
            })

        await send({
            'type': 'http.response.body',
            'body': start_body,
            'more_body': True
        })
        for start, end in ranges:
            await send({
                'type': 'http.response.body',
                'body': create_sub_header(start, end),
                'more_body': True
            })
            await self.send_file(send, self.path, start, end)

            await send({
                'type': 'http.response.body',
                'body': f'\n--{boundary}\n'.encode('latin-1'),
                'more_body': True
            })
        return await send({
            'type': 'http.response.body',
            'body': b''
        })

    async def call(self, scope: Scope, receive: Receive, send: Send):
        await self.setup()
        send_header_only = scope["method"].upper() == "HEAD"
        http_range, http_if_range = "", ""
        for key, value in scope["headers"]:
            if key == b"range":
                http_range = value.decode("latin-1")
            elif key == b"if-range":
                http_if_range = value.decode("latin-1")
        if http_range == '' or (http_if_range != "" and self.check_if_range(http_if_range, self.file_mtime, self.file_size)):
            return await self.handle_all(send_header_only, scope, send)

        try:
            # 获取range区间段, 获取失败则返回异常相关的 start 和 body部分
            ranges = self.parse_range(http_range, self.file_size)
        except (MalformedRangeHeaderError, RangeNotSatisfiableError) as http_except:
            await send({
                'type': 'http.response.start',
                'status': http_except.status_code,
                'headers': self.to_raw_headers(http_except.headers)
            })
            return await send({
                'type': 'http.response.body',
                'body': http_except.detail.encode('utf-8') if http_except else b''
            })
        if len(ranges) == 1:
            start, end = ranges[0]
            return await self.handle_single_range(send_header_only, scope, send, start, end)
        else:
            return await self.handle_multiple_range(send_header_only, scope, send, ranges)

    async def done(self):
        ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.call(scope, receive, send)
            if self.background is not None:
                await self.background()
        finally:
            await self.done()
