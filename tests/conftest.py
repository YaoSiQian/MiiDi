import sys
from pathlib import Path

# Add project root to sys.path so evals module can be imported
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
