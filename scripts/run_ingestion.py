#!/usr/bin/env python3
"""
Start the ForestGuard TCP Ingestion Service.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ingestion.main import main

if __name__ == "__main__":
    sys.exit(main())
