import os
import sys

# Add project root to sys.path so backend.main can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
