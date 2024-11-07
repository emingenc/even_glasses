# setup.py
from setuptools import setup, find_packages

setup(
    name='even_glasses',
    version='0.1.07',
    author='Emin Genc',
    author_email='emingench@gmail.com',
    description='A Python package for managing even-realities glasses devices via BLE.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/emingenc/even_glasses',
    packages=find_packages(),
    install_requires=[
        'bleak>=0.22.3',  
        'pydantic>=2.9.2',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',
)