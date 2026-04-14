# Productive.io MCP Server
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![](https://badge.mcpx.dev?type=server&features=tools 'MCP server with features')

A Model Context Protocol (MCP) server for integrating Productive.io into AI workflows. This server allows AI assistants and tools to access projects, tasks, pages and teams. Built with [FastMCP](https://gofastmcp.com/).

This implementation is tailored for read-only operations, providing streamlined access to essential data while minimizing token consumption using TOON as output. It is optimized for efficiency and simplicity, exposing only the necessary information. For a more comprehensive solution, consider BerwickGeek's implementation: [Productive MCP by BerwickGeek](https://github.com/berwickgeek/productive-mcp).

<a href="https://glama.ai/mcp/servers/@druellan/Productive-GET-MCP">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@druellan/Productive-GET-MCP/badge" alt="Productive Simple MCP server" />
</a>

## Features

- **Get Projects**: Retrieve all projects with basic information
- **Get Tasks**: Retrieve tasks with filtering and pagination
- **Get Task**: Retrieve a specific task by internal ID
- **Get Comments**: Retrieve comments with filtering
- **Get Pages**: Retrieve pages/documents with filtering
- **Get Page**: Retrieve a specific page/document by ID
- **Get Attachments**: Retrieve attachments/files with filtering
- **Get Todos**: Retrieve todo checklist items with filtering
- **Get Todo**: Retrieve a specific todo by ID
- **Get Recent Updates**: Summarized activity feed for status updates
- **Quick Search**: Fast, comprehensive search across projects, tasks, pages, and actions
- **LLM-Optimized Responses**: Filtered output removes noise, strips HTML, and reduces token consumption

## Requirements

- Python 3.8+
- Productive API token
- FastMCP 2.0+

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
- `OUTPUT_FORMAT`: Output format for tool responses ("toon" or "json", default: "toon")

## Usage

### Direct Python Execution (Recommended)
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

### Using UV
```json
    "productive": {
      "command": "uv",
      "args": [
        "--directory", "<path-to-productive-mcp>",
        "run", "server.py"
      ],
      "env": {
        "PRODUCTIVE_API_KEY": "<api-key>",
        "PRODUCTIVE_ORGANIZATION": "<organization-id"
      }
    },
```

## Available Tools

### `get_projects`
Retrieve all projects with basic information.

**Properties:**
- No parameters (returns all projects)

### `get_tasks`
Retrieve tasks with optional filtering and pagination.

**Properties:**
- `project_id` (int, optional): Filter tasks by Productive project ID
- `user_id` (int, optional): Filter tasks by assignee/user ID
- `page_number` (int, optional): Page number for pagination
- `page_size` (int, optional): Page size for pagination (default: 50)
- `sort` (str, optional): Sort parameter (e.g., 'last_activity_at', '-last_activity_at', 'created_at', 'due_date')
- `extra_filters` (dict, optional): Additional Productive API filters (e.g., `{'filter[status][eq]': 1}` for open tasks, `{'filter[status][eq]': 2}` for closed tasks)

### `get_task`
Retrieve a specific task by its internal ID. Returns task details including title, description, status, dates, **time tracking metrics** (`initial_estimate`, `worked_time`, `billable_time`, `remaining_time`), and todo counts.

**Properties:**
- `task_id` (int): The unique Productive task identifier (internal ID, e.g., 14677418)

---

### `get_task_history`
Retrieve the full history for a specific task, including status changes, assignment history, milestones, and activity summary.

**Properties:**
- `task_id` (int): The unique Productive task identifier (internal ID, e.g., 14677418)
- `hours` (int, optional): Number of hours to look back for activity history (default: 720 = 30 days, max: 8760)

**Returns:**
- `status_history`: Timeline of status changes with timestamps (from/to status and changed_at)
- `assignment_history`: Assignment changes showing who was assigned and when (assigned_to and changed_at)
- `milestones`: Key deliverables and completion markers from comments and activities
- `activity_summary`: Counts of comments, changes, status updates, assignments, and milestones

**Example:**
```python
get_task_history(14677921)  # Default 30-day history
get_task_history(14677921, hours=168)  # Last week only
get_task_history(14677921, hours=24)  # Last 24 hours
```


### `get_comments`
Retrieve comments with optional filtering and pagination.

**Properties:**
- `project_id` (int, optional): Filter comments by Productive project ID
- `task_id` (int, optional): Filter comments by Productive task ID
- `page_number` (int, optional): Page number for pagination
- `page_size` (int, optional): Page size for pagination
- `extra_filters` (dict, optional): Additional Productive API filters (e.g., `{'filter[discussion_id]': '123'}`)

### `get_pages`
Retrieve pages/documents with optional filtering and pagination.

**Properties:**
- `project_id` (int, optional): Filter pages by Productive project ID
- `creator_id` (int, optional): Filter pages by creator ID
- `page_number` (int, optional): Page number for pagination
- `page_size` (int, optional): Page size for pagination

### `get_page`
Retrieve a specific page/document by ID.

**Properties:**
- `page_id` (int): The unique Productive page identifier

### `get_attachments`
Retrieve attachments/files with optional filtering and pagination.

**Properties:**
- `page_number` (int, optional): Page number for pagination
- `page_size` (int, optional): Page size for pagination
- `extra_filters` (dict, optional): Additional Productive API filters

### `get_recent_activity`
Get a summarized feed of recent activities and updates. Perfect for status updates.

**Properties:**
- `hours` (int, optional): Number of hours to look back (default: 24, use 168 for a week)
- `user_id` (int, optional): Filter by specific user/person ID
- `project_id` (int, optional): Filter by specific project ID
- `activity_type` (int, optional): Filter by activity type (1: Comment, 2: Changeset, 3: Email)
- `item_type` (str, optional): Filter by item type (e.g., 'Task', 'Page', 'Deal', 'Workspace')
- `event_type` (str, optional): Filter by event type (e.g., 'create', 'copy', 'update', 'delete')
- `task_id` (int, optional): Filter by specific task ID
- `max_results` (int, optional): Maximum number of activities to return (default: 100, max: 200)

### `get_todos`
Retrieve todo checklist items with optional filtering and pagination.

**Properties:**
- `task_id` (int, optional): Filter todos by Productive task ID
- `page_number` (int, optional): Page number for pagination
- `page_size` (int, optional): Page size for pagination
- `extra_filters` (dict, optional): Additional Productive API filters

### `quick_search`
Quick search across projects, tasks, pages, and actions.

**Properties:**
- `query` (str): Search query string
- `search_types` (list[str], optional): List of types to search (action, project, task, page). Defaults to all.
- `deep_search` (bool, optional): Whether to perform deep search (default: True)
- `page` (int, optional): Page number for pagination (default: 1)
- `per_page` (int, optional): Results per page (default: 50)

**Description:**
Provides fast, comprehensive search across all Productive content types including projects, tasks, pages, and actions. It's optimized for quick lookups and general search queries.

**Response Format:**
Returns filtered results optimized for LLM consumption with only essential fields:
- `record_id`: Unique identifier for the resource
- `record_type`: Type of resource (project, task, page, etc.)
- `title`: Display title (with search highlights removed)
- `subtitle`: Additional context or description
- `icon_url`: URL to the resource's icon/avatar (if available)
- `status`: Current status (active, closed, etc.)
- `project_name`: Name of the associated project
- `updated_at`: Last update timestamp
- `webapp_url`: Direct link to view the resource in Productive web interface

**Examples:**
```python
quick_search("deployment")  # Search for "deployment" across all content types
quick_search("meeting notes", search_types=["project"])  # Search only in projects
quick_search("this week summary", deep_search=False)  # Quick search without deep scan
```

### `get_todo`
Retrieve a specific todo checklist item by ID.

**Properties:**
- `todo_id` (int): The unique Productive todo checklist item identifier

## Output Format

All tools return filtered data optimized for LLM processing. The output format can be configured via the `OUTPUT_FORMAT` environment variable:

- **JSON**: Standard JSON format for compatibility with existing tools and workflows
- **TOON** (default): Token-Optimized Object Notation reduces token consumption by 30-60% compared to JSON, ideal for LLM interactions

All tools return filtered data optimized for LLM processing:

**LLM Optimizations:**
- Unwanted fields removed (e.g., `creation_method_id`, `email_key`, `placement` from tasks)
- HTML stripped from descriptions and comments
- Empty/null values removed
- Pagination links removed
- List views use lightweight output (e.g., `get_project_tasks` excludes descriptions and relationships)
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
