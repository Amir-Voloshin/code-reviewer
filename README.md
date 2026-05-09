# AI PR Reviewer

An AI agent that automatically reviews pull requests using [LangGraph](https://github.com/langchain-ai/langgraph), the [GitHub MCP server](https://github.com/github/github-mcp-server), and any LLM you choose. When it finds bugs or security issues, it opens a second PR with the fixes applied.

```
PR opened
    └─► AI reviews diff (LangGraph + GitHub MCP)
          └─► Posts inline review comments
                ├── No issues → Done
                └── Issues found → Creates fix branch → Applies fixes → Opens fix PR
```

## How it works

1. A GitHub Actions workflow triggers on every `pull_request` event
2. The LangGraph agent fetches the PR diff via the GitHub MCP server
3. The review node uses structured output to produce typed inline comments
4. If fixes are needed, a ReAct fix agent reads each file, applies minimal changes, and commits them to a new branch
5. A fix PR is opened targeting the original PR's base branch

## Quick start

### 1. Fork this repository

Everything runs inside GitHub Actions — no server or hosting required.

### 2. Enable Actions write permissions

Go to **Settings → Actions → General → Workflow permissions** and select:
- **Read and write permissions**
- **Allow GitHub Actions to create and approve pull requests**

### 3. Add repository secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add one secret at a time.

You need exactly **3 secrets**: the two required ones + the API key for your chosen provider.

| Secret | Example value | When to add |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Always (required) |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | Always (required) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Only if `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | `sk-...` | Only if `LLM_PROVIDER=openai` |
| `GEMINI_API_KEY` | `AI...` | Only if `LLM_PROVIDER=google-genai` |

> `GITHUB_TOKEN` is injected automatically by GitHub Actions — do **not** add it as a secret.

### 4. Open a PR

Create any branch with code changes and open a PR. The **AI PR Reviewer** workflow starts automatically. Check the **Actions** tab to watch it run.

---

## Supported models

Change `LLM_PROVIDER` and `LLM_MODEL` to switch models with no code changes.

| Provider | `LLM_PROVIDER` | Example `LLM_MODEL` |
|---|---|---|
| Anthropic | `anthropic` | `claude-sonnet-4-6` |
| OpenAI | `openai` | `gpt-4.1` |
| Google | `google-genai` | `gemini-2.5-pro` |

---

## Local development

```bash
# Clone and install
git clone https://github.com/your-username/pr-reviewer.git
cd pr-reviewer
pip install -r requirements.txt

# Copy and fill in env vars
cp .env.example .env
# edit .env with your tokens and PR details

# Run against a real PR
source .env
python entrypoint.py
```

### Smoke tests

```bash
# 1. Verify the GitHub MCP server starts
npx -y @modelcontextprotocol/server-github

# 2. Verify MCP tool loading
python - <<'EOF'
import asyncio
from agent.tools import make_mcp_client

async def test():
    async with make_mcp_client() as client:
        tools = await client.get_tools()
        print(f"Loaded {len(tools)} tools:")
        for t in tools[:10]:
            print(f"  {t.name}")

asyncio.run(test())
EOF

# 3. Verify LLM connection
python - <<'EOF'
from agent.model import get_llm
llm = get_llm()
print(llm.invoke("Say hello in one word.").content)
EOF
```

---

## Project structure

```
pr-reviewer/
├── .github/workflows/pr-review.yml   # Actions trigger
├── agent/
│   ├── graph.py                      # LangGraph StateGraph
│   ├── nodes.py                      # Node implementations
│   ├── state.py                      # PRReviewState TypedDict
│   ├── tools.py                      # GitHub MCP client factory
│   └── model.py                      # Model-agnostic LLM factory
├── prompts/
│   ├── reviewer.md                   # Review agent system prompt
│   └── fixer.md                      # Fix agent system prompt
├── entrypoint.py                     # CLI entry point
└── requirements.txt
```

---

## Design notes

**Why LangGraph?** The review flow is a directed graph with conditional branching (fix or don't fix). LangGraph's `StateGraph` makes the control flow explicit and inspectable.

**Why structured output for review, ReAct for fix?** The review decision has a bounded, predictable shape — structured output is more reliable. Applying fixes is inherently iterative (read → patch → write, repeat) so a tool-use ReAct loop is the right fit.

**Why GitHub MCP?** The official GitHub MCP server exposes 50+ GitHub API operations as typed tools. The agent discovers and calls them without any custom API client code.

**Why `pull_request` not `pull_request_target`?** `pull_request_target` grants write permissions to fork PRs but checks out the base branch code, not the PR's code — a GitHub security boundary. This repo is scoped to same-repo PRs where `pull_request` works cleanly. For cross-fork support, replace `secrets.GITHUB_TOKEN` with a PAT stored as `GH_PAT`.

---

## Optional: LangSmith tracing

Add these secrets to enable full agent trace visibility in [LangSmith](https://smith.langchain.com):

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=pr-reviewer
```

Then add them to the `env:` block in `.github/workflows/pr-review.yml`.
