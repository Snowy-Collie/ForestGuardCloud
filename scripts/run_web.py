#!/usr/bin/env python3
"""
Start the ForestGuard FastAPI Web Backend.
"""

import sys
import uvicorn
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config.settings import get_web_settings

if __name__ == "__main__":
    settings = get_web_settings()
    uvicorn.run("src.web_backend.app:app", host=settings.server.host, port=settings.server.port, reload=True)
