from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

import chainlit as cl


# Create a supervisor graph
async def create_multi_agent_graph():
    """Create a LangGraph graph with a supervisor and MCP servers."""
    checkpointer = InMemorySaver()
    store = InMemoryStore()
    ollama_chat_llm = ChatOllama(
        base_url="http://localhost:11435",
        model="llama3.1:8b",
        temperature=0.0
    )

    client = MultiServerMCPClient(
        {
            "pubmed": {
                "url": "http://localhost:3017/mcp",
                "transport": "streamable_http",
            },
            "google-scholar": {
                "url": "http://localhost:3001/mcp",
                "transport": "streamable_http"
            }
        }
    )
    search_tools = await client.get_tools()
    search_agent = create_agent(
        model=ollama_chat_llm,
        tools=[search_tools],
        system_prompt=(
            "You are a medical research agent. \n\n"
            "INSTRUCTIONS:\n"
            "- Assist ONLY with research related tasks, DO NOT do anything else\n"
            "- After you're done with your tasks,  respond to the supervisor directly\n"
            "- Respond ONLY with the results of your work\n"
            "- Add a tag to the message so the source can be traced\n"
            "- do NOT include ANY other text."
        ),
        name="search_agent",
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "search_tools": {"allowed_decisions": ["approve", "reject"]}},
                # Prefix for interrupt messages - combined with tool name and args to form the full message
                # e.g., "Tool execution pending approval: execute_sql with query='DELETE FROM...'"
                # Individual tools can override this by specifying a "description" in their interrupt config
                description_prefix="Tool execution pending approval",
            ),
        ],
        checkpointer=checkpointer,
    )

    # Create the supervisor
    supervisor = create_supervisor(
        agents=[search_agent],
        model=ollama_chat_llm,
        prompt=(
            "You are a supervisor managing one agent:\n"
            "- a search agent.\n"
            "INSTRUCTIONS:\n"
            "- Assign search of article and medical abstract related tasks to the search agent\n"
            "- Do formatting of the text or other related queries related to formatting of the results"
            "- Don't do any other work yourself."
        ),
        add_handoff_back_messages=False,
        output_mode="last_message",
    )
    return supervisor.compile(checkpointer=checkpointer, store=store)


@cl.on_message
async def run(msg: cl.Message):
    graph = await create_multi_agent_graph()

    config = {"configurable": {"thread_id": cl.context.session.id}}
    cb = cl.LangchainCallbackHandler()
    final_answer = cl.Message(content="")
    async for messages, metadata in graph.astream({"messages": [HumanMessage(content=msg.content)]}, stream_mode="messages", config=RunnableConfig(callbacks=[cb], **config)):
        if (
                messages.content
                and not isinstance(messages, HumanMessage)
        ):
            await final_answer.stream_token(messages.content)

    await final_answer.send()

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


# Example usage
if __name__ == "__main__":
    main()
