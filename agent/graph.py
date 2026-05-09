from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    make_apply_fixes_node,
    make_create_fix_branch_node,
    make_fetch_pr_node,
    make_handle_error_node,
    make_open_fix_pr_node,
    make_post_review_node,
    make_review_agent_node,
)
from agent.state import PRReviewState


def _route_after_review(state: PRReviewState) -> Literal["create_fix_branch", "handle_error", "__end__"]:
    if state.get("error"):
        return "handle_error"
    if state.get("needs_fix"):
        return "create_fix_branch"
    return END


def _route_after_fetch(state: PRReviewState) -> Literal["review_agent", "handle_error"]:
    if state.get("error"):
        return "handle_error"
    return "review_agent"


def build_graph(tools: list):
    tools_by_name = {t.name: t for t in tools}

    g = StateGraph(PRReviewState)

    g.add_node("fetch_pr", make_fetch_pr_node(tools_by_name))
    g.add_node("review_agent", make_review_agent_node())
    g.add_node("post_review", make_post_review_node(tools_by_name))
    g.add_node("create_fix_branch", make_create_fix_branch_node(tools_by_name))
    g.add_node("apply_fixes", make_apply_fixes_node(tools))
    g.add_node("open_fix_pr", make_open_fix_pr_node(tools_by_name))
    g.add_node("handle_error", make_handle_error_node(tools_by_name))

    g.add_edge(START, "fetch_pr")
    g.add_conditional_edges(
        "fetch_pr",
        _route_after_fetch,
        {"review_agent": "review_agent", "handle_error": "handle_error"},
    )
    g.add_edge("review_agent", "post_review")
    g.add_conditional_edges(
        "post_review",
        _route_after_review,
        {
            "create_fix_branch": "create_fix_branch",
            "handle_error": "handle_error",
            END: END,
        },
    )
    g.add_edge("create_fix_branch", "apply_fixes")
    g.add_edge("apply_fixes", "open_fix_pr")
    g.add_edge("open_fix_pr", END)
    g.add_edge("handle_error", END)

    return g.compile()
