import asyncssh
from fastapi import FastAPI

from fastapi_range_response import AsyncsshRangeResponse

app = FastAPI()


@app.get('/')
async def test_download():
    ssh_client = await asyncssh.connect(host='xxxx', port=22, username='root', password='xxxx!')
    return AsyncsshRangeResponse('/root/web.py', ssh_client, media_type='application/octet-stream')


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
