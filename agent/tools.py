import os

from langchain_mcp_adapters.client import MultiServerMCPClient


def make_mcp_client() -> MultiServerMCPClient:
    token = os.environ["GITHUB_TOKEN"]
    return MultiServerMCPClient(
        {
            "github": {
                "transport": "stdio",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-github",
                ],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": token,
                },
            }
        }
    )
