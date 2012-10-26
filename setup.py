from setuptools import setup, find_packages

setup(
    name='server-reloader',
    version='0.1.0',
    description='Provides easy way to reload you server on code changes or another events',
    keywords='server code reload reloader restarter',
    license = 'New BSD License',
    author="Alexander Artemenko",
    author_email='svetlyak.40wt@gmail.com',
    url='http://github.com/svetlyak40wt/server-reloader/',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(),
)
