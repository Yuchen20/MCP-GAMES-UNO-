import asyncio
from mcp_agent.core.fastagent import FastAgent

# Create the application
fast = FastAgent("memory-enhanced-agent")

@fast.agent(
    instruction="""You are a helpful AI Agent with memory capabilities. 
    You can record, retrieve, and manage memories using the memory MCP server.
    Use the memory commands to store and recall information as needed.""",
    servers=["memory_server"]
)
async def main():
    async with fast.run() as agent:
        # Example of using memory capabilities
        await agent.interactive()

if __name__ == "__main__":
    asyncio.run(main())
