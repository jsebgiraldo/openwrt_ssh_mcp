"""Chat CLI that bridges a local OpenAI-compatible endpoint with the OpenWRT MCP server.

Provides a natural language interface to your OpenWRT router using a local LLM
(Ollama, LM Studio, vLLM, LocalAI, etc.) instead of Claude Desktop or Copilot.

Usage:
    openwrt-mcp-chat
    python -m openwrt_ssh_mcp.chat

Configuration (set in .env):
    OPENAI_BASE_URL    - Your local endpoint (default: http://localhost:11434/v1)
    OPENAI_API_KEY     - API key (default: "ollama")
    OPENAI_MODEL       - Model name (default: "llama3.2")
    OPENAI_MAX_TOKENS  - Max tokens per response (default: 4096)
    OPENAI_TEMPERATURE - LLM temperature (default: 0.0)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from openai import AsyncOpenAI

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

from .config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt - sets context for the LLM
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an OpenWRT router management assistant. You have access to tools that let you manage an OpenWRT router via SSH.

Available tool categories:
- System & Network: test connection, execute commands, get system info, restart interfaces, wifi status, DHCP leases, firewall rules, UCI config
- OpenThread Border Router: Thread network state, create network, get dataset, get info, enable commissioner
- Package Management: opkg update, install, remove, list packages, package info

Rules:
1. For questions about the router's status, use the appropriate tool first, then summarize the results clearly.
2. Only use tools when you need to interact with the router. For general questions, answer directly.
3. When executing commands, prefer the specialized tools over openwrt_execute_command.
4. Always format responses clearly and concisely.
"""


# ---------------------------------------------------------------------------
# MCP Tool to OpenAI Tool Mapping
# ---------------------------------------------------------------------------


def mcp_tool_to_openai_tool(mcp_tool: Any) -> dict[str, Any]:
    """Convert an MCP Tool definition to OpenAI tool calling format."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": mcp_tool.inputSchema,
        },
    }


# ---------------------------------------------------------------------------
# Async input helper
# ---------------------------------------------------------------------------


async def ainput(prompt: str = "") -> str:
    """Read a line from stdin asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: input(prompt).strip())


# ---------------------------------------------------------------------------
# Conversation history management
# ---------------------------------------------------------------------------


def prune_messages(messages: list[dict], max_messages: int = 60) -> list[dict]:
    """Keep conversation within bounds by dropping oldest non-system exchanges."""
    if len(messages) <= max_messages:
        return messages
    system = [m for m in messages if m["role"] == "system"]
    others = [m for m in messages if m["role"] != "system"]
    return system + others[-(max_messages - len(system)):]


def format_tool_args(args: dict[str, Any]) -> str:
    """Format tool arguments for display."""
    if not args:
        return ""
    return json.dumps(args, ensure_ascii=False)


def format_tool_result(result_text: str, max_len: int = 300) -> str:
    """Truncate tool results for tool-call result display."""
    if len(result_text) <= max_len:
        return result_text
    return result_text[:max_len] + f"\n... [truncated, {len(result_text)} total chars]"


# ---------------------------------------------------------------------------
# Tool calling cycle
# ---------------------------------------------------------------------------


async def execute_tool_calls(
    session: ClientSession,
    msg: Any,
    history: list[dict],
    openai_tools: list[dict],
    client: AsyncOpenAI,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str | None:
    """Execute tool calls from the LLM response, feed results back, return final text.

    Handles the full tool-calling loop: one or more tools may be called in
    parallel by the LLM. Each tool is executed and its result is appended to
    the conversation history. The LLM is then called again with the results
    until it produces a final text response.
    """
    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [],
    }

    for tc in msg.tool_calls:
        assistant_msg["tool_calls"].append({
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        })

    history.append(assistant_msg)

    # Execute each tool call
    for tc in msg.tool_calls:
        tool_name = tc.function.name
        try:
            tool_args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            tool_args = {}

        args_display = format_tool_args(tool_args)
        if args_display:
            print(f"  [Tool] {tool_name}({args_display})")
        else:
            print(f"  [Tool] {tool_name}()")
        sys.stdout.flush()

        result_text = ""
        try:
            result = await session.call_tool(tool_name, tool_args)
            if hasattr(result, "content") and result.content:
                parts = []
                for c in result.content:
                    if hasattr(c, "text"):
                        parts.append(c.text)
                    else:
                        parts.append(str(c))
                result_text = "".join(parts)
            elif isinstance(result, dict):
                result_text = json.dumps(result, indent=2, ensure_ascii=False)
            else:
                result_text = str(result)

            is_error = getattr(result, "isError", False)
            if is_error:
                print(f"  [Tool Error] {format_tool_result(result_text)}")
        except Exception as e:
            result_text = json.dumps({"error": str(e)}, ensure_ascii=False)
            print(f"  [Tool Exception] {e}")

        # Truncate very long tool outputs to avoid blowing context
        history.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result_text[:8000] if result_text else "(no output)",
        })

    history = prune_messages(history)

    # Get next response from LLM with tool results
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=history,
            tools=openai_tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        next_msg = response.choices[0].message

        # If the LLM wants to call more tools, recurse
        if next_msg.tool_calls:
            return await execute_tool_calls(
                session=session,
                msg=next_msg,
                history=history,
                openai_tools=openai_tools,
                client=client,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        return next_msg.content

    except Exception as e:
        print(f"\n[API Error during tool result processing] {e}")
        return None


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------


async def run_chat_loop(
    session: ClientSession,
    client: AsyncOpenAI,
    model: str,
    max_tokens: int,
    temperature: float,
) -> None:
    """Run the interactive chat loop."""
    tools_result = await session.list_tools()
    openai_tools = [mcp_tool_to_openai_tool(t) for t in tools_result.tools]

    print(f"\n{'='*60}")
    print(f"  OpenWRT MCP Chat")
    print(f"  Router:   {settings.openwrt_user}@{settings.openwrt_host}:{settings.openwrt_port}")
    print(f"  LLM:      {model} @ {settings.openai_base_url}")
    print(f"  Tools:    {len(openai_tools)} available")
    print(f"{'='*60}")
    print("  Type /quit or /exit to stop, /tools to list tools, /new to reset")
    print("  Commands: use natural language to manage your router\n")

    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = await ainput("\n>> ")
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("/quit", "/exit"):
            print("Goodbye!")
            break

        if cmd == "/tools":
            print(f"\nAvailable tools ({len(openai_tools)}):")
            for t in openai_tools:
                fn = t["function"]
                params = fn["parameters"].get("properties", {})
                required = fn["parameters"].get("required", [])
                print(f"  \u2022 {fn['name']}")
                if fn["description"]:
                    desc = fn["description"][:120]
                    print(f"    {desc}")
                if params:
                    p_str = ", ".join(params.keys())
                    print(f"    Params: {p_str}")
                    if required:
                        print(f"    Required: {', '.join(required)}")
                print()
            continue

        if cmd == "/new":
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("  Conversation reset.")
            continue

        # Add user message to history
        history.append({"role": "user", "content": user_input})
        history = prune_messages(history)

        # Send to LLM
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=history,
                tools=openai_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            print(f"\n[API Error] {e}")
            history.pop()
            continue

        choice = response.choices[0]
        msg = choice.message

        # Handle tool calling if the LLM requests tools
        if msg.tool_calls:
            final_content = await execute_tool_calls(
                session=session,
                msg=msg,
                history=history,
                openai_tools=openai_tools,
                client=client,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        else:
            final_content = msg.content

        if final_content:
            print(f"\n{final_content}")

        # Add the final assistant message to history
        history.append({"role": "assistant", "content": final_content or ""})
        history = prune_messages(history)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main_async() -> None:
    """Async entry point: start MCP server subprocess and chat loop."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openwrt_ssh_mcp.server"],
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                client = AsyncOpenAI(
                    base_url=settings.openai_base_url,
                    api_key=settings.openai_api_key,
                )

                await run_chat_loop(
                    session=session,
                    client=client,
                    model=settings.openai_model,
                    max_tokens=settings.openai_max_tokens,
                    temperature=settings.openai_temperature,
                )
    except FileNotFoundError:
        print(f"Error: Python executable not found at {sys.executable}")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting MCP server: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point for the chat CLI."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
