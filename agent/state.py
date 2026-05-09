from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class PRReviewState(TypedDict):
    messages: Annotated[list, add_messages]

    # PR context (populated from environment variables at start)
    pr_number: int
    repo_owner: str
    repo_name: str
    pr_head_branch: str
    pr_base_branch: str

    # Populated by fetch_pr node
    pr_diff: str
    pr_title: str
    pr_body: str

    # Populated by review_agent node
    review_comments: list[dict]
    needs_fix: bool
    fix_description: str

    # Populated by fix nodes
    fix_branch_name: str
    fix_pr_url: str

    # Error propagation
    error: str | None
