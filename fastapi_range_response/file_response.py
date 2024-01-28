import os
import stat
from typing import Optional, Mapping, Union

import aiofiles
from starlette.background import BackgroundTask
from starlette.types import Send

from fastapi_range_response._base import BaseRangeResponse


class FileRangeResponse(BaseRangeResponse):

    def __init__(self,
                 path: str,
                 *,
                 media_type: Optional[str] = None,
                 download_name: Optional[str] = None,
                 headers: Optional[Mapping[str, str]] = None,
                 background: Optional[BackgroundTask] = None,
                 chunk_size: int = 1024 * 256
                 ) -> None:
        self.stat_result: Optional[os.stat_result] = None
        super().__init__(path, media_type=media_type, download_name=download_name, headers=headers, background=background, chunk_size=chunk_size)

    @property
    def file_mtime(self) -> Union[float, int]:
        return self.stat_result.st_mtime

    @property
    def file_size(self) -> int:
        return self.stat_result.st_size

    async def setup(self):
        self.stat_result = os.stat(self.path)
        if stat.S_ISDIR(self.stat_result.st_mode):
            raise IsADirectoryError(f"{self.path} is a directory")
        await super().setup()

    async def send_file(self, send: Send, path: str, start: int, end: int):
        async with aiofiles.open(path, 'rb') as f:
            await f.seek(start)
            for sub_start, sub_end in self.parse_chunks(start, end):
                await send({
                    'type': 'http.response.body',
                    'body': await f.read(sub_end + 1 - sub_start),
                    'more_body': True
                })
