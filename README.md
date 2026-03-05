# Jira MCP Server (Dockerized + MCP CLI Ready)

## 1. Create `.env` file

JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_api_token_here

## 2. Start

docker compose up --build

## 3. MCP CLI Integration

Open `mcp-config.json` and replace:

/ABSOLUTE/PATH/TO/jira-mcp

with the real absolute path.

Merge into your MCP config and restart your MCP app.
