from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='fastapi_range_response',
    version='0.1.1',
    description='HTTP range implementation based on Fastapi',
    author='wyh',
    author_email='2448979539@qq.com',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=['fastapi_range_response'],
    install_requires=[
        'requests',
        'starlette',
        'asyncssh',
        'aiofiles'
    ],
    python_requires='>=3.10'
)
