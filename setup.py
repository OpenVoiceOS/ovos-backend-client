from setuptools import setup

setup(
    name='selene_api',
    version='0.0.2post1',
    packages=['selene_api'],
    url='https://github.com/OpenVoiceOS/selene_api',
    license='Apache2',
    author='jarbasai',
    install_requires=["ovos_utils>=0.0.25a4"],
    author_email='jarbasai@mailfence.com',
    description='unofficial api for selene backend'
)
