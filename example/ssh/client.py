import asyncio

import aiohttp


async def handle_all():
    async with aiohttp.request(method='get', url='http://127.0.0.1:8000') as response:
        print(response.headers)
        print(await response.text())


async def handle_single_range():
    headers = {
        'Range': 'bytes=0-'
    }
    async with aiohttp.request(method='get', url='http://127.0.0.1:8000', headers=headers) as response:
        print(response.headers)
        print(await response.text())


async def handle_multiple_range():
    headers = {
        'Range': 'bytes=0-100,101-200,201-'
    }
    async with aiohttp.request(method='get', url='http://127.0.0.1:8000', headers=headers) as response:
        print(response.headers)
        body = await response.text()
        print(body.encode())
        print(body.replace('\r', ''), end='')

if __name__ == '__main__':
    asyncio.run(handle_all())
    # asyncio.run(handle_single_range())
    # asyncio.run(handle_multiple_range())
