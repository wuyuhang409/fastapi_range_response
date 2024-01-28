# Fastapi Range Response


## Description
- HTTP range response for Fastapi
- Part of the code is based on changes to [BáiZé](https://github.com/abersheeran/baize) FileResponse
- 实现了[HTTP Range](https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests)的响应类, 继承自starlette.response.Response, 可使用本机文件或sftp协议进行读取文件

## Install

```
pip install fastapi_range_response
```

## QuickStart
A short example for fastapi application

```python
import asyncio
import asyncssh
from fastapi import FastAPI
from fastapi import Query
from fastapi_range_response import FileRangeResponse, AsyncsshRangeResponse

app = FastAPI()


@app.get('/local_file')
async def download_local_file(full_path: str = Query()):
    return FileRangeResponse(full_path, media_type='application/octet-stream')


@app.get('/download_sftp_file')
async def download_sftp_file(full_path: str = Query()):
    ssh_client = await asyncio.wait_for(
        asyncssh.connect(host='xxx', port=22, username='xxx', password='xxxx', known_hosts=None),
        timeout=10
    )
    return AsyncsshRangeResponse(full_path, ssh_client, done_close=True)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
```