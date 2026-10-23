import os
import sys
import json
import asyncio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Inherit current Windows environment with required flags
SERVER_ENV = {
    **os.environ,
    "PYTHONUNBUFFERED": "1",
    "PYTHONPATH": ".",
    "TQDM_DISABLE": "1",
    "TRANSFORMERS_VERBOSITY": "error",
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    "TOKENIZERS_PARALLELISM": "false",
}

@pytest.mark.asyncio
async def test_profile_rag_mcp_server_via_client():
    """
    Spawns profile_rag_server as a subprocess over stdio,
    discovers its tools via MCP protocol, and executes search_profile.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_servers.profile_rag_server"],
        env=SERVER_ENV
    )

    # Wrap in timeout so test never hangs silently
    async with asyncio.timeout(60.0):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. Discover registered tools dynamically
                tools_response = await session.list_tools()
                tool_names = [t.name for t in tools_response.tools]
                assert "search_profile" in tool_names
                assert "get_faq_answer" in tool_names

                # 2. Call tool through MCP JSON-RPC protocol
                result = await session.call_tool(
                    name="search_profile",
                    arguments={"query": "FastAPI", "top_k": 1}
                )

                assert len(result.content) > 0
                tool_output = json.loads(result.content[0].text)
                assert isinstance(tool_output, list)
                assert len(tool_output) == 1
                assert "chunk_id" in tool_output[0]


@pytest.mark.asyncio
async def test_job_search_mcp_server_via_client():
    """
    Spawns job_search_server as a subprocess over stdio,
    discovers tools, and queries job details.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_servers.job_search_server"],
        env=SERVER_ENV
    )

    async with asyncio.timeout(20.0):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. Discover tools
                tools_response = await session.list_tools()
                tool_names = [t.name for t in tools_response.tools]
                assert "get_matched_jobs" in tool_names
                assert "get_job_details" in tool_names

                # 2. Discover available jobs dynamically
                list_result = await session.call_tool(
                    name="get_matched_jobs",
                    arguments={"limit": 5}
                )
                assert len(list_result.content) > 0
                jobs_list = json.loads(list_result.content[0].text)

                if jobs_list:
                    target_job_id = jobs_list[0]["id"]
                    result = await session.call_tool(
                        name="get_job_details",
                        arguments={"job_id": target_job_id}
                    )
                    assert len(result.content) > 0
                    job_data = json.loads(result.content[0].text)
                    assert job_data["id"] == target_job_id
                    assert "title" in job_data
