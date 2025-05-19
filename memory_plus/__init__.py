"""
Memory Plus - A memory management server using FastMCP
"""

__version__ = "0.1.0"

from .memory_protocol import MemoryProtocol
from .mcp import mcp, main
from .utils import get_app_dir, get_user_uuid, get_whether_to_annonimize, log_message

__all__ = [
    'MemoryProtocol',
    'mcp',
    'main',
    'get_app_dir',
    'get_user_uuid',
    'get_whether_to_annonimize',
    'log_message'
]

if __name__ == "__main__":
    main()
