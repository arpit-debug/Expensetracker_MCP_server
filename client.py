import asyncio
from dotenv import load_dotenv

from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()


async def main():

    print("Starting MCP client...")

    client = MultiServerMCPClient(
        {
            "expense_tracker": {
                "command": "python",
                "args": ["main.py"],
                "transport": "stdio",
            }
        }
    )

    print("Connecting to MCP server...")

    tools = await client.get_tools()

    print(f"Loaded {len(tools)} tools")

    for tool in tools:
        print("Tool:", tool.name)

    llm = ChatOllama(
        model="qwen2.5",
        temperature=0,
    )

    print("Creating agent...")

    agent = create_agent(
        model=llm,
        tools=tools,
    )

    print("Running agent...")

    response = await agent.ainvoke(
        {
            "messages": [
                (
                    "user",
                    "Add expense of 500 on 2026-05-16 in Food category for pizza"
                )
            ]
        }
    )

    print("\n========== AGENT EXECUTION ==========\n")

    for msg in response["messages"]:

        print(f"\nTYPE: {msg.__class__.__name__}")

        if hasattr(msg, "content"):
            print("CONTENT:")
            print(msg.content)

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print("\nTOOL CALLS:")
            for tc in msg.tool_calls:
                print(tc)

    print("\n========== FINAL ANSWER ==========\n")

    print(response["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())