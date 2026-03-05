# Installation

## Create `.env` file

```
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_api_token_here
```

## Create a virtual environment 
```
cd PROJECT_FOLDER
python3 -m venv .venv
```

## Activate it
```
source .venv/bin/activate
```

## Install dependencies
```
pip install fastmcp requests python-dotenv
```

## Freeze the requirements
```
pip freeze > requirements.txt
```

## Test it
```
python3 server.py
```

You should see

`Starting MCP server 'jira-mcp-server' with transport 'stdio'`

# Configure OpenCode
```
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "jira": {
      "type": "local",
       "command": [
	       "PATH_TO_YOUR_MCP_PROJECT/.venv/bin/python",
	       "PATH_TO_YOUR_MCP_PROJECT/server.py"
      ],
      "enabled": true
    }
  }
}
```
