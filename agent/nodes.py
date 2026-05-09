import json
import logging
import time
from pathlib import Path
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from agent.model import get_llm
from agent.state import PRReviewState

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# --------------------------------------------------------------------------- #
# Pydantic models for structured LLM output
# --------------------------------------------------------------------------- #


class InlineComment(BaseModel):
    path: str
    line: int
    body: str


class ReviewDecision(BaseModel):
    comments: list[InlineComment]
    needs_fix: bool
    fix_description: str


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _parse(result) -> dict | list:
    # MCP tools return content blocks: [{"type": "text", "text": "<json>"}]
    if isinstance(result, list) and result and isinstance(result[0], dict) and result[0].get("type") == "text":
        result = result[0]["text"]
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw": result}
    return {}


def _tool(tools_by_name: dict, name: str):
    tool = tools_by_name.get(name)
    if tool is None:
        available = list(tools_by_name.keys())
        raise RuntimeError(f"MCP tool '{name}' not found. Available: {available}")
    return tool


# --------------------------------------------------------------------------- #
# Node factories
# --------------------------------------------------------------------------- #


def make_fetch_pr_node(tools_by_name: dict) -> Callable:
    async def fetch_pr(state: PRReviewState) -> dict:
        log.info("fetch_pr: fetching PR #%s", state["pr_number"])
        try:
            pr_tool = _tool(tools_by_name, "get_pull_request")
            files_tool = _tool(tools_by_name, "get_pull_request_files")

            params = {
                "owner": state["repo_owner"],
                "repo": state["repo_name"],
                "pull_number": state["pr_number"],
            }

            pr_raw = await pr_tool.ainvoke(params)
            files_raw = await files_tool.ainvoke(params)

            pr_data = _parse(pr_raw)
            files_data = _parse(files_raw)

            # Build unified diff text from per-file patches
            diff_parts: list[str] = []
            if isinstance(files_data, list):
                for f in files_data:
                    if isinstance(f, dict):
                        filename = f.get("filename", "")
                        patch = f.get("patch", "")
                        if patch:
                            diff_parts.append(f"--- a/{filename}\n+++ b/{filename}\n{patch}")

            pr_diff = "\n\n".join(diff_parts) if diff_parts else "(no diff available)"

            title = pr_data.get("title", "") if isinstance(pr_data, dict) else ""
            body = pr_data.get("body", "") or "" if isinstance(pr_data, dict) else ""

            log.info("fetch_pr: fetched %d changed files", len(diff_parts))
            return {"pr_diff": pr_diff, "pr_title": title, "pr_body": body}

        except Exception as exc:
            log.error("fetch_pr failed: %s", exc)
            return {"error": str(exc)}

    return fetch_pr


def make_review_agent_node() -> Callable:
    async def review_agent(state: PRReviewState) -> dict:
        if state.get("error"):
            return {}

        log.info("review_agent: reviewing PR #%s", state["pr_number"])
        try:
            system_prompt = (_PROMPTS_DIR / "reviewer.md").read_text()
            llm = get_llm()
            structured_llm = llm.with_structured_output(ReviewDecision)

            human_content = (
                f"**PR Title:** {state['pr_title']}\n\n"
                f"**PR Description:**\n{state['pr_body'] or '(none)'}\n\n"
                f"**Diff:**\n```diff\n{state['pr_diff']}\n```"
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
            ]

            decision: ReviewDecision = await structured_llm.ainvoke(messages)

            log.info(
                "review_agent: %d comment(s), needs_fix=%s",
                len(decision.comments),
                decision.needs_fix,
            )
            return {
                "review_comments": [c.model_dump() for c in decision.comments],
                "needs_fix": decision.needs_fix,
                "fix_description": decision.fix_description,
                "messages": [
                    AIMessage(
                        content=(
                            f"Review complete. {len(decision.comments)} issue(s) found. "
                            f"needs_fix={decision.needs_fix}."
                        )
                    )
                ],
            }

        except Exception as exc:
            log.error("review_agent failed: %s", exc)
            return {"error": str(exc)}

    return review_agent


def make_post_review_node(tools_by_name: dict) -> Callable:
    async def post_review(state: PRReviewState) -> dict:
        if state.get("error"):
            return {}

        log.info("post_review: posting review on PR #%s", state["pr_number"])
        try:
            review_tool = _tool(tools_by_name, "create_pull_request_review")
            comments = state.get("review_comments", [])

            if comments:
                event = "COMMENT"
                body = (
                    f"## AI Code Review\n\n"
                    f"Found **{len(comments)}** issue(s) that need attention.\n\n"
                    f"{state.get('fix_description', '')}"
                )
                github_comments = [
                    {"path": c["path"], "line": c["line"], "side": "RIGHT", "body": c["body"]}
                    for c in comments
                ]
            else:
                event = "APPROVE"
                body = "## AI Code Review\n\nLGTM — no issues found. :white_check_mark:"
                github_comments = []

            params = {
                "owner": state["repo_owner"],
                "repo": state["repo_name"],
                "pull_number": state["pr_number"],
                "body": body,
                "event": event,
                "comments": github_comments,
            }
            await review_tool.ainvoke(params)
            log.info("post_review: review posted with event=%s", event)
            return {}

        except Exception as exc:
            log.error("post_review failed: %s", exc)
            return {"error": str(exc)}

    return post_review


def make_create_fix_branch_node(tools_by_name: dict) -> Callable:
    async def create_fix_branch(state: PRReviewState) -> dict:
        if state.get("error"):
            return {}

        branch_name = f"ai-review/{state['pr_number']}-{int(time.time())}"
        log.info("create_fix_branch: creating branch %s", branch_name)
        try:
            branch_tool = _tool(tools_by_name, "create_branch")
            await branch_tool.ainvoke(
                {
                    "owner": state["repo_owner"],
                    "repo": state["repo_name"],
                    "branch": branch_name,
                    "from_branch": state["pr_head_branch"],
                }
            )
            log.info("create_fix_branch: branch created")
            return {"fix_branch_name": branch_name}

        except Exception as exc:
            log.error("create_fix_branch failed: %s", exc)
            return {"error": str(exc)}

    return create_fix_branch


def make_apply_fixes_node(tools: list) -> Callable:
    async def apply_fixes(state: PRReviewState) -> dict:
        if state.get("error"):
            return {}

        log.info("apply_fixes: running fix agent on branch %s", state["fix_branch_name"])
        try:
            system_prompt = (_PROMPTS_DIR / "fixer.md").read_text()
            llm = get_llm()
            fix_agent = create_react_agent(llm, tools, state_modifier=system_prompt)

            task = (
                f"Apply the following code review fixes to the repository.\n\n"
                f"**Repository:** {state['repo_owner']}/{state['repo_name']}\n"
                f"**Target branch:** {state['fix_branch_name']}\n\n"
                f"**Review issues to fix:**\n"
                + json.dumps(state["review_comments"], indent=2)
                + f"\n\n**Original diff for context:**\n```diff\n{state['pr_diff']}\n```\n\n"
                f"For each issue: use `get_file_contents` to read the file, make the minimal "
                f"fix, then use `push_files` to commit it to branch `{state['fix_branch_name']}`."
            )

            await fix_agent.ainvoke({"messages": [HumanMessage(content=task)]})
            log.info("apply_fixes: fix agent completed")
            return {}

        except Exception as exc:
            log.error("apply_fixes failed: %s", exc)
            return {"error": str(exc)}

    return apply_fixes


def make_open_fix_pr_node(tools_by_name: dict) -> Callable:
    async def open_fix_pr(state: PRReviewState) -> dict:
        if state.get("error"):
            return {}

        log.info("open_fix_pr: opening fix PR")
        try:
            pr_tool = _tool(tools_by_name, "create_pull_request")

            body = (
                f"## AI-Generated Fixes for PR #{state['pr_number']}\n\n"
                f"{state.get('fix_description', 'Automated fixes based on code review.')}\n\n"
                f"---\n"
                f"*This PR was opened automatically by the AI PR Reviewer agent.*"
            )
            result_raw = await pr_tool.ainvoke(
                {
                    "owner": state["repo_owner"],
                    "repo": state["repo_name"],
                    "title": f"AI Review Fixes for PR #{state['pr_number']}",
                    "body": body,
                    "head": state["fix_branch_name"],
                    "base": state["pr_base_branch"],
                }
            )
            result = _parse(result_raw)
            fix_pr_url = result.get("html_url", "") if isinstance(result, dict) else ""
            log.info("open_fix_pr: PR opened at %s", fix_pr_url)
            return {"fix_pr_url": fix_pr_url}

        except Exception as exc:
            log.error("open_fix_pr failed: %s", exc)
            return {"error": str(exc)}

    return open_fix_pr


def make_handle_error_node(tools_by_name: dict) -> Callable:
    async def handle_error(state: PRReviewState) -> dict:
        error_msg = state.get("error", "Unknown error")
        log.error("handle_error: %s", error_msg)
        try:
            comment_tool = tools_by_name.get("create_issue_comment")
            if comment_tool:
                await comment_tool.ainvoke(
                    {
                        "owner": state["repo_owner"],
                        "repo": state["repo_name"],
                        "issue_number": state["pr_number"],
                        "body": (
                            f"## AI PR Reviewer — Error\n\n"
                            f"The review agent encountered an error and could not complete.\n\n"
                            f"```\n{error_msg[:500]}\n```"
                        ),
                    }
                )
        except Exception:
            pass
        return {}

    return handle_error
