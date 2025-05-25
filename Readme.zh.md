
![memory\_plus](https://memory-plus.imgix.net/memory_plus.png)

![精美图片](https://memory-plus.imgix.net/memory_server_banner.png)

[![许可证：MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE) ![访客数](https://visitor-badge.laobi.icu/badge?page_id=Yuchen20.Memory-Plus) [![PyPI 版本](https://badge.fury.io/py/memory-plus.svg)](https://pypi.org/project/memory-plus/) [![PyPI 下载量](https://static.pepy.tech/badge/memory-plus)](https://pepy.tech/projects/memory-plus)

# Memory-Plus

Memory-Plus 是一个轻量级的本地 RAG（检索增强生成）记忆存储系统，专为 MCP 智能体设计。它允许你的智能体在多次运行中记录、检索、更新并可视化“记忆”——包括笔记、想法和上下文信息。

> 🏆 **荣获 [Infosys 剑桥 AI 中心黑客松大赛](https://infosys-cam-ai-centre.github.io/Infosys-Cambridge-Hackathon/)第一名！**

## 核心功能

* **记录记忆**：保存用户数据、想法和重要上下文信息。
* **检索记忆**：支持通过关键词或主题搜索过往的记忆条目。
* **最近记忆**：快速获取最近的 *N* 条记忆。
* **更新记忆**：可无缝追加或修改已有记忆内容。
* **可视化记忆**：通过交互式图谱聚类展示记忆之间的关联关系。
* **文件导入**（自 v0.1.2 起）：支持将文档直接导入记忆系统中。
* **删除记忆**（自 v0.1.2 起）：删除不再需要的记忆条目。
* **元记忆系统**（自 v0.1.4 起）：借助 `resources` 教会 AI 何时该（或不该）回忆过去的交互内容。
* **记忆版本控制**（自 v0.1.4 起）：在更新记忆时保留历史版本，完整记录记忆的演变过程。

---

![记忆图谱可视化](https://memory-plus.imgix.net/memory_visualization.png)

## 安装指南

### 1. 先决条件

**Google API 密钥**
前往 [Google AI Studio](https://aistudio.google.com/apikey) 获取并设置为环境变量 `GOOGLE_API_KEY`。

> 我们只使用该密钥访问 `Gemini Embedding API`，**完全免费**！

<details>
<summary><b>Google API 密钥设置示例</b></summary>

```bash
# macOS/Linux
export GOOGLE_API_KEY="<你的 API 密钥>"

# Windows（PowerShell）
setx GOOGLE_API_KEY "<你的 API 密钥>"
```

</details>

**UV 运行时**
用于运行 MCP 插件。

<details>
<summary><b>安装 UV 运行时</b></summary>

```bash
pip install uv
```

或者使用 shell 脚本安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows（PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

</details>

### VS Code 一键安装

点击以下徽章可在 VS Code 中自动安装并配置 Memory-Plus：

[![在 VS Code 中一键安装](https://img.shields.io/badge/VS_Code-UV-0098FF?style=flat-square\&logo=visualstudiocode\&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=memory-plus&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22-q%22%2C%22memory-plus%40latest%22%5D%7D)

这将会在你的 `settings.json` 中添加以下配置：

```json
{
  "mcpServers": {
    //...,  其他 MCP 服务
    "memory-plus": {
      "command": "uvx",
      "args": [
        "-q",
        "memory-plus@latest"
      ]
    }
  }
}
```

如果你使用 `cursor` 编辑器，请进入 `文件 -> 偏好设置 -> Cursor 设置 -> MCP` 添加以上配置。

若你尚未设置 `GOOGLE_API_KEY` 环境变量，可以在配置中添加：

```json
"env": {
  "GOOGLE_API_KEY": "<你的 API 密钥>"
}
```

将其添加在 `args` 数组之后。

对于 `Cline` 用户，请在 `cline_mcp_settings.json` 中加入以下内容：

```json
{
  "mcpServers": {
    //...,  其他 MCP 服务
    "memory-plus": {
      "disabled": false,
      "timeout": 300,
      "command": "uvx",
      "args": [
        "-q",
        "memory-plus@latest"
      ],
      "env": {
        "GOOGLE_API_KEY": "${{ secrets.GOOGLE_API_KEY }}"
      },
      "transportType": "stdio"
    }
  }
}
```

对于其他 IDE，配置方式大致类似。

## 本地测试与开发

使用 MCP Inspector 工具，你可以在本地测试 memory-plus 服务。

```bash
git clone https://github.com/Yuchen20/Memory-Plus.git
cd Memory-Plus
npx @modelcontextprotocol/inspector fastmcp run run .\\memory_plus\\mcp.py
```

或者，如果你希望在实际对话中使用 Memory-Plus，可以使用 `agent.py` 中的聊天模板：

```bash
# 克隆仓库
git clone https://github.com/Yuchen20/Memory-Plus.git
cd Memory-Plus

# 安装依赖
pip install uv
uv pip install fast-agent-mcp
uv run fast-agent setup        
```

配置 `fastagent.config.yaml` 和 `fastagent.secrets.yaml` 文件，填入你自己的 API 密钥。

```bash
# 运行聊天代理
uv run agent_memory.py
```

## 未来规划

* [x] 支持记忆更新
* [x] 优化记忆记录提示词
* [x] 更好的记忆图谱可视化
* [x] 文件导入功能
* [ ] 远程备份功能！
* [ ] 管理记忆的网页界面

> 如果你有功能需求，欢迎通过提交 issue 或在 [功能请求页面](https://voltaic-shell-9af.notion.site/1f84e395c1d18059849ce844fcbba903?pvs=105)中添加新建议！

## 许可证

本项目使用 **Apache License 2.0** 授权。详情见 [LICENSE](./LICENSE)。

## 常见问题（FAQ）

### 1. 为什么 memory-plus 没有正常工作？
- memory-plus 依赖一些外部库，首次加载时可能较慢，通常需要约 1 分钟来下载所有依赖项。
- 下载完成后，后续使用会更快。
- 如果遇到其他问题，欢迎在项目页面提交新的 issue。

### 2. 如何在真实对话中使用 memory-plus？
- 只需将 MCP 的 JSON 文件添加到你的 MCP 设置中。
- 添加后，memory-plus 会在需要时自动启用。
