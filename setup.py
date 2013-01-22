# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

version = '0.2'

setup(name='pyremotezip',
	version=version,
	description="Extract files from remote ZIP archives",
	long_description=""" """,
	classifiers=[],
	keywords="",
	author="Filipe Varela",
	author_email="fcvarela@gmail.com",
	url="https://github.com/fcvarela/pyremotezip/",
	license="BSD",
	package_dir={'': '.'},
	packages=find_packages(where='.'),
	include_package_data=True,
	zip_safe=False,
	install_requires=['setuptools',],
	entry_points="""
	# None whatsoever
	""",
)
