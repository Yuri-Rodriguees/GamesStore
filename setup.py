# setup.py
from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("uxmod", ["uxmod.py"]),
    Extension("xcore", ["xcore.py"]),
    Extension("datax", ["datax.py"]),
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={'language_level': "3"}
    )
)
