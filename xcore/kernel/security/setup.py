"""
setup.py — Build de l'extension C++ scanner_core.

Usage :
    python setup.py build_ext --inplace   # développement
    pip install .                          # production

L'extension est placée à côté de validation.py pour que l'import
`from .scanner_core import ImportClassifier` fonctionne directement.
"""

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ext = Pybind11Extension(
    name="scanner_core",
    sources=["scanner_core.cpp"],
    cxx_std=17,  # std::filesystem nécessite C++17
    extra_compile_args=[
        "-O3",  # optimisation max
        "-march=native",  # instructions CPU locales
        "-fvisibility=hidden",  # réduit la taille du .so
    ],
)

setup(
    name="scanner_core",
    version="1.0.0",
    ext_modules=[ext],
    cmdclass={"build_ext": build_ext},
)
