from tarfile import version

from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
import logging

import chainlit as cl

logger = logging.getLogger("__NAME__")

# Create a supervisor graph
async def create_multi_agent_graph():
    """Create a LangGraph graph with a supervisor and MCP servers."""
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
    # for t in search_tools:
    #     logger.info(f"!!!! {t.get_name()}")
    search_agent = create_agent(
        model=ollama_chat_llm,
        tools=search_tools,
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
                    "search_tools": {"allowed_decisions": ["approve", "reject"]},
                    "pubmed_article_connections": {"allowed_decisions": ["approve", "reject"]},
                    "pubmed_fetch_contents": {"allowed_decisions": ["approve", "reject"]},
                    "pubmed_generate_chart": {"allowed_decisions": ["approve", "reject"]},
                    "pubmed_research_agent": {"allowed_decisions": ["approve", "reject"]},
                    "pubmed_search_articles": {"allowed_decisions": ["approve", "reject"]},
                    "search_google_scholar": {"allowed_decisions": ["approve", "reject"]},
                },
                description_prefix="Tool execution pending approval",
            ),
        ],
        checkpointer=MemorySaver()
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
        # middleware=[
        #     HumanInTheLoopMiddleware(
        #         interrupt_on={
        #             "search_tools": {"allowed_decisions": ["approve", "reject"]},
        #             "pubmed_article_connections": {"allowed_decisions": ["approve", "reject"]},
        #             "pubmed_fetch_contents": {"allowed_decisions": ["approve", "reject"]},
        #             "pubmed_generate_chart": {"allowed_decisions": ["approve", "reject"]},
        #             "pubmed_research_agent": {"allowed_decisions": ["approve", "reject"]},
        #             "pubmed_search_articles": {"allowed_decisions": ["approve", "reject"]},
        #             "search_google_scholar": {"allowed_decisions": ["approve", "reject"]},
        #         },
        #         description_prefix="Tool execution pending approval",
        #     ),
        # ],
        #add_handoff_back_messages=False,
        output_mode="last_message",
    )
    return supervisor.compile(checkpointer=MemorySaver())


@cl.on_message
async def run(msg: cl.Message):
    graph = await create_multi_agent_graph()

    config = {"configurable": {"thread_id": cl.context.session.id}}
    graph_state = await graph.aget_state(config={"configurable": {"thread_id": cl.context.session.id}})
    if graph_state:
        historic_messages = graph_state.values.get("messages", [])
    else:
        historic_messages = []
    historic_messages.append(msg.content)
    cb = cl.LangchainCallbackHandler()
    final_answer = cl.Message(content="")
    async for metadata, mode, chunk in graph.astream({"messages": historic_messages}, stream_mode=["updates", "messages"], subgraphs=True, config=RunnableConfig(callbacks=[cb], **config)):
        logger.info(f"!!!! mode: {mode} \n\n chunk: {chunk} \n\n\n\n")
        if (
                mode == "messages"
                #and not isinstance(messages, HumanMessage)
        ):
            token, _ = chunk
            if not isinstance(token, HumanMessage):
                await final_answer.stream_token(token.content)
        elif mode == "updates":
            # Check for interrupt
            if "__interrupt__" in chunk:
                logger.info(f"!!!!! \n\n\n\nInterrupt: {chunk['__interrupt__']}\n\n\n\n\n")



    await final_answer.send()

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


# Example usage
if __name__ == "__main__":
    main()
