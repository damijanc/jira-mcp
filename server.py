import os
import requests
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
    raise ValueError("Missing Jira environment variables")

mcp = FastMCP("jira-mcp-server")


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
        raise Exception(
            f"Jira API error {response.status_code}: {response.text}"
        )

    if response.text:
        return response.json()
    return {"success": True}


def format_issue(issue):
    return {
        "key": issue["key"],
        "summary": issue["fields"]["summary"],
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


@mcp.tool()
def get_issue(issue_key: str) -> dict:
    """Fetch a single Jira issue by key (e.g. PROJ-123)"""
    issue = jira_request("GET", f"issue/{issue_key}")
    return format_issue(issue)


@mcp.tool()
def search_issues(jql: str, max_results: int = 10) -> dict:
    """Search Jira issues using JQL"""
    data = jira_request(
        "GET",
        "search",
        params={
            "jql": jql,
            "maxResults": max_results,
        },
    )

    return {
        "total": data["total"],
        "issues": [format_issue(i) for i in data["issues"]],
    }


@mcp.tool()
def add_comment(issue_key: str, comment: str) -> dict:
    """Add a comment to a Jira issue"""
    body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment}],
                }
            ],
        }
    }

    jira_request(
        "POST",
        f"issue/{issue_key}/comment",
        json=body,
    )

    return {"success": True, "issue": issue_key}


if __name__ == "__main__":
    mcp.run()
