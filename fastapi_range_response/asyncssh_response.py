from typing import Optional, Mapping, Union

import asyncssh
from starlette.background import BackgroundTask
from starlette.types import Send

from fastapi_range_response._base import BaseRangeResponse


class AsyncsshRangeResponse(BaseRangeResponse):

    def __init__(self,
                 path: str,
                 ssh_client: asyncssh.SSHClientConnection,
                 *,
                 media_type: Optional[str] = None,
                 download_name: Optional[str] = None,
                 headers: Optional[Mapping[str, str]] = None,
                 background: Optional[BackgroundTask] = None,
                 chunk_size: int = 1024 * 256,
                 done_close: bool = True
                 ) -> None:
        self.ssh_client: asyncssh.SSHClientConnection = ssh_client
        self.stat_result: Optional[asyncssh.sftp.SFTPAttrs] = None
        self.done_close = done_close
        super().__init__(path, media_type=media_type, download_name=download_name, headers=headers, background=background, chunk_size=chunk_size)

    @property
    def file_mtime(self) -> Union[float, int]:
        return self.stat_result.mtime

    @property
    def file_size(self) -> int:
        return self.stat_result.size

    async def setup(self):
        async with self.ssh_client.start_sftp_client() as sftp_client:
            self.stat_result = await sftp_client.stat(self.path)
            if await sftp_client.isdir(self.path):
                raise IsADirectoryError(f"{self.path} is a directory")
        await super().setup()

    async def done(self):
        if self.done_close:
            self.ssh_client.close()
            await self.ssh_client.wait_closed()

    async def send_file(self, send: Send, path: str, start: int, end: int):
        async with self.ssh_client.start_sftp_client() as sftp_client:
            async with sftp_client.open(self.path, 'rb') as f:
                f: asyncssh.sftp.SFTPClientFile
                await f.seek(start)
                for sub_start, sub_end in self.parse_chunks(start, end):
                    await send({
                        'type': 'http.response.body',
                        'body': await f.read(sub_end + 1 - sub_start),
                        'more_body': True
                    })
