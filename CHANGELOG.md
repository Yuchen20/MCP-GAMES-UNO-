# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2025-05-20
### Fixed
- Quick Fix: Fixed the issue where there is an deprecated import in `mcp.py` and `__init__.py`


## [0.1.3] - 2025-05-20

### Fixed
- Enhanced error handling to return error messages instead of raising exceptions
- Removed a problematic print statement from the main function that could lead to
```
[error] user-memory-plus:     print('memory server started')
user-memory-plus: ValueError: I/O operation on closed file.
```

### Changed
- Improved Prompt Engineering: Enhanced the system prompt for what kind of memories to record


## [0.1.2] - 2025-05-19

### Added
- File Import: Importing memories from files
- Delete Memories: Deleting memories from the memory store
- Memory for Memories: A JSON file containing categories and tags for memories, enabling LLM to understand when to retrieve or not retrieve memories
- One-Click Setup for VS Code: Simplifying the setup process for VS Code users
- Python Package on PyPI: Uploading the python package to PyPI for easier access to MCP

### Fixed
- Qdrant Server Connection: Resolved the issue where the Qdrant server was occupied by the Memory-Plus server, allowing only one client to connect at a time
    - Solution: Utilizing a 'with' clause for connection

### Changed
- Prompt Engineering: Enhanced prompt engineering for better interaction
- MetaData: Improved MetaData for enhanced recording and understanding of recorded memories
- Readme: Updated Readme with detailed instructions on using the Memory-Plus server