import os
import requests
from fastmcp import FastMCP
from dotenv import load_dotenv
from pathlib import Path

# Load .env relative to file
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    raise ValueError("Missing Jira environment variables")

mcp = FastMCP("jira-mcp-server")


# ============================================================
# Core Request Helper
# ============================================================

def jira_request(method: str, endpoint: str, params=None, json=None):
    url = f"{JIRA_BASE_URL}/rest/api/3/{endpoint}"

    response = requests.request(
        method=method,
        url=url,
        params=params,
        json=json,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Accept": "application/json"},
    )

    if not response.ok:
        return {
            "error": True,
            "status": response.status_code,
            "message": response.text,
        }

    if response.text:
        return response.json()

    return {"success": True}


# ============================================================
# Utilities
# ============================================================

def extract_plain_text_description(description_field):
    if not description_field:
        return None

    content = description_field.get("content", [])
    text_parts = []

    for block in content:
        for item in block.get("content", []):
            if item.get("type") == "text":
                text_parts.append(item.get("text"))

    return "\n".join(text_parts) if text_parts else None


def format_issue(issue):
    description = extract_plain_text_description(
        issue["fields"].get("description")
    )

    return {
        "key": issue["key"],
        "summary": issue["fields"]["summary"],
        "description": description,
        "status": issue["fields"]["status"]["name"],
        "assignee": (
            issue["fields"]["assignee"]["displayName"]
            if issue["fields"]["assignee"]
            else None
        ),
        "reporter": issue["fields"]["reporter"]["displayName"],
        "created": issue["fields"]["created"],
        "updated": issue["fields"]["updated"],
        "url": f"{JIRA_BASE_URL}/browse/{issue['key']}",
    }


def resolve_user_account_id(identifier: str):
    """
    Resolve accountId from email or display name.
    """
    result = jira_request(
        "GET",
        "user/search",
        params={"query": identifier}
    )

    if result.get("error"):
        return result

    if not result:
        return {"error": True, "message": "User not found"}

    return result[0]["accountId"]


def get_transition_id_by_name(issue_key: str, transition_name: str):
    result = jira_request("GET", f"issue/{issue_key}/transitions")

    if result.get("error"):
        return result

    for t in result.get("transitions", []):
        if t["name"].lower() == transition_name.lower():
            return t["id"]

    return {"error": True, "message": f"Transition '{transition_name}' not found"}


# ============================================================
# Read / Search
# ============================================================

@mcp.tool()
def get_issue(issue_key: str) -> dict:
    """Get full Jira issue including description."""
    issue = jira_request("GET", f"issue/{issue_key}")
    if issue.get("error"):
        return issue
    return format_issue(issue)


@mcp.tool()
def search_issues(jql: str, max_results: int = 10) -> dict:
    """Search Jira issues using JQL."""

    data = jira_request(
        "GET",
        "search/jql",
        params={
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,status,assignee,reporter,created,updated,description",
        },
    )

    if isinstance(data, dict) and data.get("error"):
        return data

    if "issues" not in data:
        return {
            "error": True,
            "message": "Unexpected Jira response",
            "raw_response": data,
        }

    formatted = []

    for issue in data.get("issues", []):
        if "fields" not in issue:
            return {
                "error": True,
                "message": "Jira returned issues without fields",
                "raw_issue": issue,
            }

        formatted.append(format_issue(issue))

    return {
        "total": data.get("total", 0),
        "issues": formatted,
    }


@mcp.tool()
def my_tickets(status: str | None = None) -> dict:
    """
    Get tickets assigned to current user.
    Optionally filter by status.
    """
    jql = "assignee = currentUser()"
    if status:
        jql += f' AND status = "{status}"'

    return search_issues(jql=jql, max_results=20)


# ============================================================
# Comments & Updates
# ============================================================

@mcp.tool()
def add_comment(issue_key: str, comment: str) -> dict:
    """Add a comment to a Jira issue."""
    body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": comment}],
            }],
        }
    }

    result = jira_request(
        "POST",
        f"issue/{issue_key}/comment",
        json=body,
    )

    if result.get("error"):
        return result

    return {"success": True, "issue": issue_key}


@mcp.tool()
def update_issue(
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
    append: bool = False,
) -> dict:
    """
    Update Jira issue summary or description.
    If append=True, new description text will be appended.
    """

    fields = {}

    if summary:
        fields["summary"] = summary

    if description:
        if append:
            existing = get_issue(issue_key)
            if existing.get("error"):
                return existing
            description = (existing.get("description") or "") + "\n\n" + description

        fields["description"] = {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": description}],
            }],
        }

    if not fields:
        return {"error": True, "message": "No fields provided"}

    result = jira_request(
        "PUT",
        f"issue/{issue_key}",
        json={"fields": fields},
    )

    if result.get("error"):
        return result

    return {"success": True, "issue": issue_key}


# ============================================================
# Create
# ============================================================

@mcp.tool()
def create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    assignee: str | None = None,
) -> dict:
    """
    Create new Jira issue.
    Assignee can be email or display name.
    """

    body = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
    }

    if description:
        body["fields"]["description"] = {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": description}],
            }],
        }

    if assignee:
        account_id = resolve_user_account_id(assignee)
        if isinstance(account_id, dict) and account_id.get("error"):
            return account_id
        body["fields"]["assignee"] = {"accountId": account_id}

    result = jira_request("POST", "issue", json=body)

    if result.get("error"):
        return result

    key = result["key"]

    return {"key": key, "url": f"{JIRA_BASE_URL}/browse/{key}"}


# ============================================================
# Assign
# ============================================================

@mcp.tool()
def assign_issue(issue_key: str, user: str) -> dict:
    """
    Assign issue using email or display name.
    """

    account_id = resolve_user_account_id(user)
    if isinstance(account_id, dict) and account_id.get("error"):
        return account_id

    result = jira_request(
        "PUT",
        f"issue/{issue_key}/assignee",
        json={"accountId": account_id},
    )

    if result.get("error"):
        return result

    return {"success": True, "issue": issue_key}


# ============================================================
# Transition (by Name)
# ============================================================

@mcp.tool()
def transition_issue(issue_key: str, transition_name: str) -> dict:
    """
    Transition issue by status name (e.g., Done, In Progress).
    """

    transition_id = get_transition_id_by_name(issue_key, transition_name)

    if isinstance(transition_id, dict) and transition_id.get("error"):
        return transition_id

    result = jira_request(
        "POST",
        f"issue/{issue_key}/transitions",
        json={"transition": {"id": transition_id}},
    )

    if result.get("error"):
        return result

    return {"success": True, "issue": issue_key}


# ============================================================
# Runtime Mode
# ============================================================

if __name__ == "__main__":
    mode = os.getenv("MCP_MODE", "stdio")

    if mode == "http":
        mcp.run(transport="http", host="0.0.0.0", port=8000)
    else:
        mcp.run()