from setuptools import setup, Extension
from Cython.Build import cythonize
import os

def get_extensions():
    extensions = []
    
    # Arquivos raiz a serem compilados
    # main.py e setup.py geralmente não são compilados dessa forma ou precisam de tratamento especial
    root_files = [
        'uxmod.py', 
        'xcore.py', 
        'datax.py', 
        'utils.py', 
        'updater.py', 
        'ui_components.py', 
        'config.py', 
        'rc.py'
    ]
    
    for file in root_files:
        if os.path.exists(file):
            module_name = os.path.splitext(file)[0]
            extensions.append(Extension(module_name, [file]))
            
    # Compilar recursivamente o diretório core
    if os.path.exists("core"):
        for root, dirs, files in os.walk("core"):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    
                    # Converter caminho para nome de módulo: core\app.py -> core.app
                    module_path = os.path.splitext(full_path)[0]
                    module_name = module_path.replace(os.sep, ".")
                    
                    extensions.append(Extension(module_name, [full_path]))
                
    return extensions

setup(
    name="GamesStore Modules",
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives={'language_level': "3", 'always_allow_keywords': True},
        build_dir="build"
    ),
)
