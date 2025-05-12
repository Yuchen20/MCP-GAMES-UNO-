<!-- Badges -->


![memory_plus](https://github.com/Yuchen20/Memory_MCP_Server/blob/main/imgs/memory_plus.png)


![pretty image](https://github.com/Yuchen20/Memory_MCP_Server/blob/main/imgs/memory_server_banner.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)   ![visitors](https://visitor-badge.laobi.icu/badge?page_id=Yuchen20.Memory-Plus)

## Introduction
**fastmcp‑memory** provides a local RAG‑backed memory store for your MCP agent, so it can record, retrieve, list, and visualize “memories” (notes, ideas, context) across sessions. Think of it as a lightweight personal knowledge base that your agent consults and updates automatically.
> 🏆 This repo won **First Place** in the [Infosys Cambridge AI Centre Hackathon](https://infosys-cam-ai-centre.github.io/Infosys-Cambridge-Hackathon/)!

## Features
- **Record Memories**: Persist user data, ideas, or important context for future runs.  
- **Retrieve Memories**: Keyword‑ or topic‑based search over past entries.  
- **Recent Memories**: Quickly see the last _N_ stored items.  
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
1. set the api key in fastagent.secrets.yaml
2. add a `.env` file in the root directory and set the `GOOGLE_API_KEY=<your-api-key-here>`
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
      "args": ["run", "absolute/path/to/memory.py"]
    }
  }
}
```


## 🧠 One-Line Import

If you have past information—such as emails, chats, or AI conversations—that you'd like to store in the memory server, simply export them as a text file and run the following one-liner:

```bash
python load_text_to_memory.py path/to/your/previous_memory.txt
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

