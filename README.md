# Productive.io MCP Server
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![](https://badge.mcpx.dev?type=server&features=tools 'MCP server with features')
[![Productive-Simple-MCP MCP server](https://glama.ai/mcp/servers/druellan/Productive-Simple-MCP/badges/score.svg)](https://glama.ai/mcp/servers/druellan/Productive-Simple-MCP)

A Model Context Protocol (MCP) server for integrating Productive.io into AI workflows. This server allows AI assistants and tools to access projects, folders, workflow statuses, time entries, tasks, comments, pages, attachments, todos, and people. Built with [FastMCP](https://gofastmcp.com/).

This implementation is optimized for read-focused operations, with optional guarded write capabilities (for example, task creation) and LLM-friendly output options (Hybrid, JSON, and TOON). It is optimized for efficiency and simplicity, exposing only the necessary information. For a more comprehensive solution, consider BerwickGeek's implementation: [Productive MCP by BerwickGeek](https://github.com/berwickgeek/productive-mcp).

## Features

- **Read tools** for projects, folders, workflow statuses, time entries, tasks, comments, pages, attachments, todos, people, recent activity, and quick search
- **Write tools** (blocked when `READ_ONLY=true`): create/update/delete for tasks, comments, time entries, pages, and todos, plus page content append
- **LLM-optimized responses**: noise removed, HTML stripped, `webapp_url` included for direct access
- **Output formats**: `hybrid` (default), `toon`, and `json`

## Requirements

- Python 3.10+
- Productive API token
- FastMCP 3.x

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
or
```bash
uv venv && uv sync
```

## Configuration

The server uses environment variables for configuration:

- `PRODUCTIVE_API_KEY`: Your Productive API token (required)
- `PRODUCTIVE_ORGANIZATION`: Your Productive organization ID (required)
- `PRODUCTIVE_BASE_URL`: Base URL for Productive API (default: https://api.productive.io/api/v2)
- `PRODUCTIVE_TIMEOUT`: Request timeout in seconds (default: 30)
- `PRODUCTIVE_ITEMS_PER_PAGE`: Default page size for list tools (default: 50, max: 200)
- `OUTPUT_FORMAT`: Output format for tool responses (`"hybrid"`, `"toon"`, or `"json"`, default: `"hybrid"`)
- `READ_ONLY`: Global write-protection toggle for write tools — create_task, update_task, delete_task, create_comment, update_comment, delete_comment, create_time_entry, update_time_entry, delete_time_entry, create_page, update_page, append_page_content, delete_page, create_todo, update_todo, delete_todo ("true" or "false", default: "true")

## Usage

### Using `uvx` from GitHub (Recommended for MCP clients)
```json
    "productive": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/druellan/Productive-Simple-MCP",
        "productive-mcp"
      ],
      "env": {
        "PRODUCTIVE_API_KEY": "<api-key>",
        "PRODUCTIVE_ORGANIZATION": "<organization-id>"
      }
    }
```

### Local Development (Direct Python Execution)
```json
    "productive": {
      "command": "python",
      "args": [
        "server.py"
      ],
      "env": {
        "PRODUCTIVE_API_KEY": "<api-key>",
        "PRODUCTIVE_ORGANIZATION": "<organization-id>"
      }
    }
```

### Local Development Using UV
```json
    "productive": {
      "command": "uv",
      "args": [
        "--directory", "<path-to-productive-mcp>",
        "run", "server.py"
      ],
      "env": {
        "PRODUCTIVE_API_KEY": "<api-key>",
        "PRODUCTIVE_ORGANIZATION": "<organization-id>"
      }
    }
```

## Available Tools

MCP clients receive the full schema and descriptions for each tool automatically. The tables below summarize them.

### Read Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all projects |
| `list_folders` | List folders in a project (`project_id` required) |
| `get_folder` | Get a folder by ID |
| `list_workflow_statuses` | List workflow statuses, optionally filtered by workflow/category |
| `list_time_entries` | List time entries with date/person/project/task/service filters |
| `list_tasks` | List tasks with filtering, sorting, and pagination |
| `get_task` | Get a task by ID, enriched with recent comments, todos, and attachments |
| `get_task_history` | Get task status/assignment history, milestones, and activity summary |
| `list_comments` | List comments, optionally filtered by project/task |
| `list_pages` | List pages/documents, optionally filtered by project/creator |
| `get_page` | Get a page by ID with readable `body_html` |
| `list_attachments` | List attachment metadata |
| `list_todos` | List todo checklist items, optionally filtered by task |
| `get_todo` | Get a todo by ID |
| `list_people` | List team members |
| `get_person` | Get a person by ID |
| `list_recent_activity` | Summarized feed of recent activities |
| `quick_search` | Search across projects, tasks, pages, and actions |

### Write Tools (blocked when `READ_ONLY=true`)

| Tool | Description |
|------|-------------|
| `create_task` / `update_task` / `delete_task` | Manage tasks |
| `create_comment` / `update_comment` / `delete_comment` | Manage comments |
| `create_time_entry` / `update_time_entry` / `delete_time_entry` | Manage time entries |
| `create_page` / `update_page` / `delete_page` | Manage pages/documents |
| `append_page_content` | Append markdown or HTML to a page |
| `create_todo` / `update_todo` / `delete_todo` | Manage todo checklist items |

## Output Format

The server supports three output formats configured via the `OUTPUT_FORMAT` environment variable:

| Mode | `content` (text) | `structured_content` | Description |
|-|-|-|-|
| **`hybrid`** (default) | TOON | JSON dict | Both TOON for token efficiency and structured data for programmatic access |
| **`toon`** | TOON | `{ "toon": toonText }` | Pure TOON (Token-Optimized Object Notation) with no dual-format overhead |
| **`json`** | JSON string | JSON dict | Standard FastMCP JSON output |

TOON (Token-Optimized Object Notation) reduces token consumption by 30-60% compared to JSON. The **hybrid** mode is the recommended default: it exposes the TOON rendering as the message text while preserving the full JSON dict as structured output, so agents that rely on structured data can still parse it programmatically.

All tools return filtered data optimized for LLM processing:

**LLM Optimizations:**
- Unwanted fields removed (e.g., `creation_method_id`, `email_key`, `placement` from tasks)
- HTML stripped from descriptions and comments
- Empty/null values removed
- Pagination links removed
- List views use lightweight output (e.g., `list_tasks` excludes descriptions and relationships)
- **Web app URLs included**: Each resource includes a `webapp_url` field linking directly to the Productive web interface

**Response Structure:**
- `data`: Main resource data (array for collections, object for single items)
- `meta`: Pagination and metadata
- `included`: Related resource data (when applicable)
- `webapp_url`: Direct link to view the resource in Productive (e.g., `https://app.productive.io/12345/tasks/67890`)


## Error Handling

The server provides comprehensive error handling:

- **401 Unauthorized**: Invalid API token
- **404 Not Found**: Resource not found
- **429 Rate Limited**: Too many requests
- **500 Server Error**: Productive API issues

All errors are logged via MCP context with appropriate severity levels.

## Security

- API tokens are loaded from environment variables
- No sensitive data is logged
- HTTPS is used for all API requests
- Error messages don't expose internal details

## License

MIT License.
