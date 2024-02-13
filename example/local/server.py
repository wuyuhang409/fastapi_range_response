from fastapi import FastAPI
from fastapi_range_response import FileRangeResponse

app = FastAPI()

@app.get('/')
async def test_download():
    return FileRangeResponse('file.txt', download_name='中文.txt', media_type='application/octet-stream')

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app)
