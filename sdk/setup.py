"""
FCM Server Client SDK — setup.py
Install with: pip install -e sdk/
"""
from setuptools import setup, find_packages

setup(
    name='fcm-server-client',
    version='1.0.0',
    description='Python client SDK for the FCM Notification Server API',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='FCM Server',
    python_requires='>=3.9',
    packages=find_packages(where='.', include=['fcm_client*']),
    install_requires=[
        'requests>=2.28',
    ],
    extras_require={
        'dev': ['pytest', 'responses'],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
