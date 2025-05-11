# Memory_MCP_Server

<!-- Badges -->
<!-- [![Build Status](https://img.shields.io/github/actions/workflow/status/your-org/your-repo/ci.yml)](https://github.com/your-org/your-repo/actions)  
[![PyPI version](https://img.shields.io/pypi/v/fastmcp-memory.svg)](https://pypi.org/project/fastmcp-memory/)   -->

![alt text](https://github.com/Yuchen20/Memory_MCP_Server/blob/main/imgs/memory_server_banner.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)  

## Table of Contents
- [Memory\_MCP\_Server](#memory_mcp_server)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Configuration](#configuration)
  - [RoadMap](#roadmap)
  - [License](#license)

## Introduction
**fastmcp‑memory** provides a local RAG‑backed memory store for your MCP agent, so it can record, retrieve, list, and visualize “memories” (notes, ideas, context) across sessions. Think of it as a lightweight personal knowledge base that your agent consults and updates automatically.

## Features
- **Record Memories**: Persist user data, ideas, or important context for future runs.  
- **Retrieve Memories**: Keyword‑ or topic‑based search over past entries.  
- **List Recent Memories**: Quickly see the last _N_ stored items.  
- **Update Memories**: Update existing memories with new information.  
- **Visualize Memory Graph**: Interactive clusters showing how memories interrelate.  

![alt text](https://github.com/Yuchen20/Memory_MCP_Server/blob/main/imgs/memory_visualization.png)


## Prerequisites
```bash
# Create & activate a virtual environment
python3 -m venv .venv  
source .venv/bin/activate  
````

## Installation

```bash
git clone https://github.com/Yuchen20/Memory_MCP_Server.git  
cd fastmcp-memory  
pip install uv
uv pip install -r requirements.txt  
```

## Usage

Run the memory service (MCP) standalone:

```bash
fastmcp run memory.py
```

Or start a local agent that uses the memory server:

```bash
uv run agent.py
```

## Configuration

Add the memory server to any MCP‑capable client by adding this to your JSON config:

```json
{
  "servers": {
    "memory_server": {
      "type": "stdio",
      "command": "fastmcp",
      "args": ["run", "memory.py"]
    }
  }
}
```

## RoadMap
- [x] Memory Update
- [x] Improved prompt engineering for memory recording
- [x] Better Visualization of Memory Graph
- [ ] Possible Graph Database Integration
- [ ] Neon/Supabase Integration
- [ ] Web UI for Memory Management

## License

This project is licensed under the **MIT License**. See [LICENSE](./LICENSE) for details.

