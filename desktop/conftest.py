import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'fakes'))

# Load the library by path: the repo root also holds the student code.py,
# which would shadow Python's own `code` module if the root were on sys.path.
_path = os.path.join(os.path.dirname(HERE), 'cmu_embedded_graphics.py')
_spec = importlib.util.spec_from_file_location('cmu_embedded_graphics', _path)
_module = importlib.util.module_from_spec(_spec)
sys.modules['cmu_embedded_graphics'] = _module
_spec.loader.exec_module(_module)
