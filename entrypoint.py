import asyncio
import logging
import os
import sys

from agent.graph import build_graph
from agent.state import PRReviewState
from agent.tools import make_mcp_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("pr-reviewer")


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        log.error("Required environment variable %s is not set.", name)
        sys.exit(1)
    return val


async def main() -> None:
    initial_state: PRReviewState = {
        "messages": [],
        "pr_number": int(_require("PR_NUMBER")),
        "repo_owner": _require("REPO_OWNER"),
        "repo_name": _require("REPO_NAME"),
        "pr_head_branch": _require("PR_HEAD_BRANCH"),
        "pr_base_branch": _require("PR_BASE_BRANCH"),
        "pr_diff": "",
        "pr_title": "",
        "pr_body": "",
        "review_comments": [],
        "needs_fix": False,
        "fix_description": "",
        "fix_branch_name": "",
        "fix_pr_url": "",
        "error": None,
    }

    log.info(
        "Starting PR review: %s/%s PR #%s",
        initial_state["repo_owner"],
        initial_state["repo_name"],
        initial_state["pr_number"],
    )

    client = make_mcp_client()
    try:
        tools = await client.get_tools()
        log.info("Loaded %d MCP tools from GitHub server", len(tools))

        graph = build_graph(tools)
        result = await graph.ainvoke(initial_state)
    finally:
        await client.close()

    if result.get("error"):
        log.error("Agent finished with error: %s", result["error"])
        sys.exit(1)
    elif result.get("fix_pr_url"):
        log.info("Review complete. Fix PR opened: %s", result["fix_pr_url"])
    else:
        log.info("Review complete. No code fixes required.")


if __name__ == "__main__":
    asyncio.run(main())
