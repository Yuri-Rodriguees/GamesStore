from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(["xcore.py", "uxmod.py", "updater.py", "datax.py"], compiler_directives={'language_level': "3"})
)

