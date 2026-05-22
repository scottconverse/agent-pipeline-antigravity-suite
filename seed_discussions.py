import json
import subprocess
import sys
import time

REPO_OWNER = "scottconverse"
REPO_NAME = "agent-pipeline-antigravity-suite"

def run_gh_cmd(args):
    """Helper to run gh CLI commands and return output/errors."""
    cmd = ["gh"] + args
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print(f"Error executing command: {' '.join(cmd)}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        return None
    return result.stdout.strip()

def enable_discussions():
    """Enable discussions using REST API PATCH on the repo."""
    print("Enabling Discussions on the repository...")
    # has_discussions is a boolean, gh REST api needs it passed as -F has_discussions=true
    output = run_gh_cmd(["api", "-X", "PATCH", f"repos/{REPO_OWNER}/{REPO_NAME}", "-F", "has_discussions=true"])
    if output is None:
        print("Failed to enable discussions. Make sure the repository exists and has discussions enabled permission.")
        return False
    print("Discussions enabled successfully.")
    return True

def get_repo_and_category_ids():
    """Query GraphQL to get repository ID and category IDs."""
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        discussionCategories(first: 10) {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    
    # We pass variables using -F in gh api graphql
    output = run_gh_cmd(["api", "graphql", "-f", f"query={query}", "-F", f"owner={REPO_OWNER}", "-F", f"name={REPO_NAME}"])
    if not output:
        return None, None
    
    try:
        data = json.loads(output)
        repo_data = data.get("data", {}).get("repository", {})
        repo_id = repo_data.get("id")
        categories = repo_data.get("discussionCategories", {}).get("nodes", [])
        
        category_map = {cat["name"]: cat["id"] for cat in categories}
        return repo_id, category_map
    except Exception as e:
        print(f"Failed to parse GraphQL response: {e}")
        print(f"Raw output: {output}")
        return None, None

def create_discussion(repo_id, category_id, title, body):
    """Mutate GraphQL to create a new discussion thread."""
    mutation = """
    mutation($repoId: ID!, $catId: ID!, $title: String!, $body: String!) {
      createDiscussion(input: {repositoryId: $repoId, categoryId: $catId, title: $title, body: $body}) {
        discussion {
          id
          url
        }
      }
    }
    """
    
    output = run_gh_cmd(["api", "graphql", "-f", f"query={mutation}", "-F", f"repoId={repo_id}", "-F", f"catId={category_id}", "-F", f"title={title}", "-F", f"body={body}"])
    if not output:
        print(f"Failed to create discussion: {title}")
        return None
        
    try:
        data = json.loads(output)
        disc_url = data.get("data", {}).get("createDiscussion", {}).get("discussion", {}).get("url")
        print(f"Created Discussion '{title}': {disc_url}")
        return disc_url
    except Exception as e:
        print(f"Failed to parse creation response: {e}")
        print(f"Raw output: {output}")
        return None

def main():
    # Force stdout to use utf-8 to print emojis correctly on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== GitHub Discussion Seeder ===")
    
    # 1. Enable discussions
    if not enable_discussions():
        sys.exit(1)
        
    # Give GitHub a second to register the change
    time.sleep(2)
    
    # 2. Get IDs
    repo_id, category_map = get_repo_and_category_ids()
    if not repo_id:
        print("Failed to retrieve Repository ID.")
        sys.exit(1)
        
    print(f"Found Repository ID: {repo_id}")
    print(f"Found Categories: {list(category_map.keys())}")
    
    # Map the categories we want (or fall back to first available if not found)
    # Default GitHub categories: "Announcements", "General", "Ideas", "Q&A", "Show and tell"
    cat_general = category_map.get("General", list(category_map.values())[0])
    cat_qa = category_map.get("Q&A", cat_general)
    cat_ideas = category_map.get("Ideas", cat_general)
    cat_show = category_map.get("Show and tell", cat_general)
    
    # Discussions details
    discussions = [
        {
            "category_id": cat_general,
            "title": "Welcome to the Antigravity Agent Pipeline Suite! 🚀",
            "body": """Hello everyone! 👋

Welcome to the official repository for the **Antigravity Agent Pipeline Suite**.

This suite brings enterprise-grade orchestration and safety to the **Antigravity** agent. By leveraging 11 custom Electron-level lifecycle hooks, it prevents context drift, manages state across compactions, and lets you execute multi-agent developer pipelines.

### What is in this repository?
1. **`agent-pipeline-antigravity`**: The main orchestration engine. Exposes `/run`, `/pipeline-init`, and `/mem0` commands.
2. **`audit-skills-antigravity`**: Single and multi-role codebase auditing tools. Exposes `/audit-lite` and `/audit-team`.
3. **`docs/`**: The responsive, dark-mode landing page detailing architecture and sequence flows.

### Getting Started
Be sure to check out our [README.md](https://github.com/scottconverse/agent-pipeline-antigravity-suite/blob/main/README.md) and [USER-MANUAL.md](https://github.com/scottconverse/agent-pipeline-antigravity-suite/blob/main/USER-MANUAL.md) for full commands and architecture diagrams.

Feel free to introduce yourself below, share how you are using the suite, and ask any questions!"""
        },
        {
            "category_id": cat_qa,
            "title": "FAQ: Memory Persistence, Hooks, and Troubleshooting 💡",
            "body": """Here is a compilation of frequently asked questions for setting up and debugging the suite.

#### Q1: What happens during an LLM compaction event?
When the context size grows too large, the host agent runs a compaction step which wipes out short-term runtime variables. The **agent-pipeline-antigravity** plugin uses the `PreCompact` hook to serialize active run states to disk (`.agent-runs/<run-id>/memory/`) and automatically re-injects them using the `PostCompact` hook, keeping the execution path uninterrupted.

#### Q2: I get permission errors when running terminal commands. How do I fix this?
Ensure that your Antigravity global permissions are properly configured. You can edit your `.gemini/config/config.json` or approve individual commands as they appear.

#### Q3: How do I customize project-specific rules?
After running `/agent-pipeline-antigravity:pipeline-init`, edit the Python policies in your project root under `scripts/policy/`:
* `check_allowed_paths.py` — restrict edit boundaries.
* `check_no_todos.py` — reject PRs containing left-behind TODO items.

Have another question? Post it in the comments below!"""
        },
        {
            "category_id": cat_ideas,
            "title": "Idea: Adding a VS Code Extension for Interactive Pipeline Monitoring 🎨",
            "body": """Currently, we monitor runs inside the terminal shell and by checking `task.md` or `.agent-runs/` logs.

**Proposed Idea:**
Build a lightweight VS Code extension that parses `.agent-runs/<run-id>/memory/state.json` in real time to show:
1. Active phase (Research, Plan, Execute, Verify, Critique)
2. Interactive checkbox lists derived from `task.md`
3. Direct approvals/replans directly from editor modals.

What do you think? Would this fit well with your workspace layout, or do you prefer the native shell environment? Share your thoughts below!"""
        },
        {
            "category_id": cat_show,
            "title": "Show and Tell: Share your custom Antigravity policy scripts! 🛠️",
            "body": """One of the most powerful features of `agent-pipeline-antigravity` is the ability to write custom python checks under `scripts/policy/` to enforce project-specific coding standards.

For example, here is a custom script that blocks any commits importing deprecated packages:

```python
# scripts/policy/check_no_deprecated.py
import sys
import glob

DEPRECATED_IMPORTS = ["import urllib", "import imp"]

for filepath in glob.glob("src/**/*.py", recursive=True):
    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, 1):
            for dep in DEPRECATED_IMPORTS:
                if dep in line:
                    print(f"Error: {filepath}:{line_num} uses deprecated import: {dep}")
                    sys.exit(1)
print("All imports clean!")
sys.exit(0)
```

Have you written any custom policies for your codebase? Share them here!"""
        }
    ]
    
    # 3. Create discussions
    for disc in discussions:
        create_discussion(repo_id, disc["category_id"], disc["title"], disc["body"])
        time.sleep(1)
        
    print("Done seeding discussions!")

if __name__ == "__main__":
    main()
