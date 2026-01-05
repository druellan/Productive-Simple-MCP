"""
Simple MCP server to access the Productive API (projects, tasks, comments, todo-lists).
Version: 0.3.0

This software is provided "as is" without warranty of any kind. Use at your own risk.
Author: druellan (druellan@ecimtech.com)
License: MIT
"""

from fastmcp import FastMCP, Context
from typing import Any, Dict, Annotated
from pydantic import Field
from config import config
from productive_client import client
import tools_read
import tools_write
from contextlib import asynccontextmanager
import json
from toon import encode as toon_encode


def output_serializer(data: Any) -> str:
    """Serialize tool output based on OUTPUT_FORMAT configuration.

    Args:
        data: The data to serialize

    Returns:
        Serialized string in the configured format (TOON or JSON)
    """
    if isinstance(data, str):
        # Don't serialize strings that are already formatted
        return data

    if config.output_format == "toon":
        try:
            return toon_encode(data)
        except Exception:
            pass

    # Default to JSON
    return json.dumps(data, indent=2, ensure_ascii=False)


@asynccontextmanager
async def lifespan(server):
    """Server lifespan context manager"""
    # Startup
    try:
        config.validate()
    except ValueError as e:
        raise ValueError(f"Configuration error: {str(e)}")

    yield

    # Shutdown
    await client.close()


mcp = FastMCP(
    name="Productive MCP Server",
    instructions=(
        "Access Productive.io data: projects, tasks, pages, comments, todos, people."
        "Use quick_search for general queries, get_recent_activity for team updates, get_task for specific tasks."
        "Use get_task_history for comprehensive task history including status changes, assignments, and milestones."
        "Use get_people to list team members and get_person for individual details."
        "All endpoints paginate (max 200 items). Use filters when possible to reduce scope."
    ),
    version="1.3.0",
    lifespan=lifespan,
    on_duplicate_tools="warn",
    on_duplicate_resources="warn",
    on_duplicate_prompts="warn",
    tool_serializer=output_serializer,
)


@mcp.tool
async def quick_search(
    ctx: Context,
    query: Annotated[str, Field(description="Search query string")],
    search_types: Annotated[
        list[str],
        Field(
            description="List of types to search (action, project, task, page). Defaults to all."
        ),
    ] = None,
    deep_search: Annotated[
        bool, Field(description="Whether to perform deep search")
    ] = True,
    page: Annotated[int, Field(description="Page number for pagination")] = 1,
    per_page: Annotated[int, Field(description="Results per page")] = 50,
) -> Dict[str, Any]:
    """Quick search across projects, tasks, pages, and actions.

    This tool provides fast, comprehensive search across all Productive content types
    including projects, tasks, pages, and actions. It's optimized for quick lookups
    and general search queries.

    Returns:
        Search results from Productive API including:
        - Matching projects, tasks, pages, and actions
        - Relevance scores and metadata
        - Full entity details for each match

    Examples:
        quick_search("red")  # Search for "red" across all content types
        quick_search("project", search_types=["project"])  # Search only in projects
        quick_search("meeting", deep_search=False)  # Quick search without deep scan
    """
    return await tools_read.quick_search(
        ctx,
        query=query,
        search_types=search_types,
        deep_search=deep_search,
        page=page,
        per_page=per_page,
    )


@mcp.tool
async def get_recent_activity(
    ctx: Context,
    hours: Annotated[
        int,
        Field(
            description="Number of hours to look back (default: 24, use 168 for a week)"
        ),
    ] = 24,
    user_id: Annotated[
        int, Field(description="Optional: Filter by specific user/person ID")
    ] = None,
    project_id: Annotated[
        int, Field(description="Optional: Filter by specific project ID")
    ] = None,
    activity_type: Annotated[
        int,
        Field(
            description="Optional: Filter by activity type (1: Comment, 2: Changeset, 3: Email)"
        ),
    ] = None,
    item_type: Annotated[
        str,
        Field(
            description="Optional: Filter by item type. Accepted values include: Task, Page, Project, Person, Discussion, TimeEntry, Section, TaskList, Dashboard, Team. Note: This list is not exhaustive."
        ),
    ] = None,
    event_type: Annotated[
        str,
        Field(
            description="Optional: Filter by event type. Common values include: create, copy, edit, delete. Note: Use get_tasks with filter[status][eq]=2 to find closed tasks."
        ),
    ] = None,
    task_id: Annotated[
        int, Field(description="Optional: Filter by specific task ID")
    ] = None,
    max_results: Annotated[
        int,
        Field(description="Optional maximum number of activities to return (max: 200)"),
    ] = None,
) -> Dict[str, Any]:
    """Get a summarized feed of recent activities and updates.

    Returns recent changes, task updates, comments, new documents and activities in chronological order.

    Examples:
        get_recent_activity()  # Last 24 hours, all activity
        get_recent_activity(hours=168)  # Last week
        get_recent_activity(hours=48, project_id=343136)  # Last 2 days on specific project
        get_recent_activity(hours=24, user_id=12345)  # What a specific user did today
        get_recent_activity(hours=24, activity_type=1)  # Only comments from last day
        get_recent_activity(hours=168, item_type='Task')  # Task activities from last week
        get_recent_activity(hours=168, event_type='edit')  # Task edits from last week
        get_tasks(extra_filters={'filter[status][eq]': 2}, sort='-updated_at', page_size=10)  # Recently closed tasks
    """
    return await tools_read.get_recent_activity(
        ctx,
        hours=hours,
        user_id=user_id,
        project_id=project_id,
        activity_type=activity_type,
        item_type=item_type,
        event_type=event_type,
        task_id=task_id,
        max_results=max_results,
    )


@mcp.tool
async def get_projects(ctx: Context) -> Dict[str, Any]:
    """Get all projects with basic information.

    Returns project data including:
    - Project ID, name, and number
    - Creation and last activity timestamps
    - Archived status (if applicable)
    - Webapp URL for direct access
    """
    return await tools_read.get_projects(ctx)


@mcp.tool
async def get_tasks(
    ctx: Context,
    project_id: Annotated[int, Field(description="Filter tasks by project ID")] = None,
    user_id: Annotated[
        int, Field(description="Filter tasks by assignee/user ID")
    ] = None,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of tasks per page (max 200)")
    ] = None,
    sort: Annotated[
        str,
        Field(
            description="Sort parameter (e.g., 'last_activity_at', '-last_activity_at', 'created_at', 'due_date'). Use '-' prefix for descending order. Defaults to '-last_activity_at' (most recent first)."
        ),
    ] = "-last_activity_at",
    extra_filters: Annotated[
        dict,
        Field(
            description="Additional Productive query filters using API syntax. Common filters: filter[status][eq] (1: open, 2: closed), filter[due_date][gte] (date), filter[workflow_status_category_id][eq] (1: not started, 2: started, 3: closed)."
        ),
    ] = None,
) -> Dict[str, Any]:
    """Get tasks with optional filtering and pagination.

    Supports filtering by project, assignee, status, and other criteria.
    All parameters are optional - omit to fetch all tasks.

    Example of extra_filters:
    - filter[status][eq]=1: Open tasks
    - filter[status][eq]=2: Closed tasks
    - filter[workflow_status_category_id][eq]=3: Workflow closed status
    - filter[board_status][eq]=1: Active board tasks

    Returns:
        Dictionary of tasks matching the provided filters
    """
    return await tools_read.get_tasks(
        ctx,
        page_number=page_number,
        page_size=page_size,
        sort=sort,
        project_id=project_id,
        user_id=user_id,
        extra_filters=extra_filters,
    )


@mcp.tool
async def get_task(
    ctx: Context,
    task_id: Annotated[
        int, Field(description="The unique Productive task identifier (internal ID)")
    ],
) -> Dict[str, Any]:
    """Get detailed task information by its internal ID.

    Use this when you have the internal task ID (e.g., 14677418).
    For looking up tasks by their project-specific number (e.g., #960), use get_project_task instead.

    Returns task details including:
    - Task title, description, and status (open/closed)
    - Due date, start date, and creation/update timestamps
    - Time tracking: initial estimate, remaining time, billable time, and worked time (in minutes)
    - Todo counts: total and open
    """
    return await tools_read.get_task(ctx=ctx, task_id=task_id)


@mcp.tool
async def get_task_history(
    ctx: Context,
    task_id: Annotated[
        int, Field(description="The unique Productive task identifier (internal ID)")
    ],
    hours: Annotated[
        int,
        Field(
            description="Number of hours to look back for activity history (default: 720 = 30 days)",
            ge=1,
            le=8760  # 1 year max
        )
    ] = 720
) -> Dict[str, Any]:
    """Get comprehensive history for a specific task.

    Returns aggregated task history including:
    - Status history: Timeline of status changes with timestamps and responsible users
    - Assignment history: Who worked on the task and when assignments changed
    - Milestones: Key deliverables and completion markers from comments and activities
    - Activity summary: Counts of comments, changes, status updates, assignments, and milestones

    Examples:
        get_task_history(14677921)  # Default 30-day history
        get_task_history(14677921, hours=168)  # Last week only
        get_task_history(14677921,1 hours=24)  # Last 24 hours
    """
    return await tools_read.get_task_history(ctx, task_id, hours)


# @mcp.tool
# async def get_project_tasks(
#     ctx: Context,
#     project_id: Annotated[
#         int, Field(description="The project ID to get tasks for")
#     ],
#     status: Annotated[
#         int, Field(description="Optional filter by task status: 1 = open, 2 = closed")
#     ] = None,
# ) -> Dict[str, Any]:
#     """Get all tasks for a specific project.

#     This is optimized for getting a comprehensive view of all tasks in a project.

#     Returns a list of all tasks in the project with details including:
#     - Task title, number, and status
#     - Assignee information
#     - Due dates and priority
#     - Task descriptions
#     - Related project context

#     Example:
#         To get all open tasks in project 343136:
#         get_project_tasks(project_id=343136, status=1)
#     """
#     return await tools.get_project_tasks(
#         ctx=ctx,
#         project_id=project_id,
#         status=status
#     )


# @mcp.tool
# async def get_project_task(
#     ctx: Context,
#     task_number: Annotated[
#         str, Field(description="The task number without # (e.g., '960')")
#     ],
#     project_id: Annotated[
#         int, Field(description="The project ID containing the task")
#     ],
# ) -> Dict[str, Any]:
#     """Get a task by its number within a specific project.

#     This is the preferred way to fetch tasks when you know the task number (e.g., #960)
#     that appears in the UI, rather than the internal database ID.

#     Task numbers are project-specific, so you must provide both the task_number and project_id.
#     For example, task #960 in project 343136.

#     Returns comprehensive task details including:
#     - Task description, priority, and current status
#     - Assigned team member with role and hourly rate
#     - Parent project with budget and client details
#     - Time tracking: estimated vs actual hours
#     - All comments and discussion history
#     - Attached files and checklist items (todos)
#     """
#     return await tools.get_project_task(
#         ctx=ctx,
#         task_number=task_number,
#         project_id=project_id
#     )


@mcp.tool
async def get_comments(
    ctx: Context,
    project_id: Annotated[
        int, Field(description="Productive project ID to filter comments by")
    ] = None,
    task_id: Annotated[
        int, Field(description="Productive task ID to filter comments by")
    ] = None,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of comments per page (max 200)")
    ] = None,
    extra_filters: Annotated[
        dict,
        Field(
            description="Additional Productive query filters using API syntax. Common filters: filter[project_id][eq] (ID), filter[task_id][eq] (ID), filter[discussion_id][eq] (ID)."
        ),
    ] = None,
) -> Dict[str, Any]:
    """Get all comments across projects and tasks with full context.

    Returns comprehensive comment data including:
    - Comment text, author, and timestamp
    - Parent entity (project, task, or other) with details
    - Discussion threads and replies
    - Attachments and file references
    - Mentions of team members or clients
    """
    return await tools_read.get_comments(
        ctx,
        project_id=project_id,
        task_id=task_id,
        page_number=page_number,
        page_size=page_size,
        extra_filters=extra_filters,
    )


# @mcp.tool
# async def get_comment(
#     ctx: Context,
#     comment_id: Annotated[int, Field(description="Productive comment ID")],
# ) -> Dict[str, Any]:
#     """Get specific comment details with full context and discussion thread.

#     Returns detailed comment information including:
#     - Complete comment text and formatting
#     - Author details and timestamp
#     - Parent entity (project, task, etc.) with full context
#     - Reply thread and conversation flow
#     - Attached files, images, or documents
#     - Mentions and references to team members

#     """
#     return await tools.get_comment(ctx, comment_id)


@mcp.tool
async def get_todos(
    ctx: Context,
    task_id: Annotated[
        int, Field(description="Productive task ID to filter todos by")
    ] = None,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of todos per page (max 200)")
    ] = None,
    extra_filters: Annotated[
        dict,
        Field(
            description="Additional Productive query filters using API syntax. Common filters: filter[task_id][eq] (ID), filter[status][eq] (1: open, 2: closed), filter[assignee_id][eq] (ID)."
        ),
    ] = None,
) -> Dict[str, Any]:
    """Get all todo checklist items across all tasks and projects.

    Returns comprehensive todo data including:
    - Checkbox items within tasks for granular tracking
    - Completion status and assignee information
    - Parent task details with project context
    - Due dates and priority relative to parent task
    - Estimated vs actual time for checklist items
    """
    return await tools_read.get_todos(
        ctx,
        task_id=task_id,
        page_number=page_number,
        page_size=page_size,
        extra_filters=extra_filters,
    )


@mcp.tool
async def get_todo(
    ctx: Context,
    todo_id: Annotated[int, Field(description="Productive todo ID")],
) -> Dict[str, Any]:
    """Get specific todo checklist item details with full task context.

    Returns detailed todo information including:
    - Checkbox item text and completion status
    - Parent task with project and client details
    - Assignee and team member information
    - Due date relative to parent task timeline
    - Time estimates vs actual completion time
    - Related comments and file attachments
    """
    return await tools_read.get_todo(ctx, todo_id)


@mcp.tool
async def get_pages(
    ctx: Context,
    project_id: Annotated[
        int, Field(description="Optional project ID to filter pages by")
    ] = None,
    creator_id: Annotated[
        int, Field(description="Optional creator ID to filter pages by")
    ] = None,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of pages per page (max 200)")
    ] = None,
) -> Dict[str, Any]:
    """Get all pages/documents with optional filtering.

    Pages in Productive are documents that can contain rich text content,
    attachments, and are organized within projects.

    Returns:
        Dictionary containing pages with content, metadata, and relationships

    Example:
        get_pages(project_id=1234)  # Get all pages for a specific project
    """
    return await tools_read.get_pages(
        ctx,
        project_id=project_id,
        creator_id=creator_id,
        page_number=page_number,
        page_size=page_size,
    )


@mcp.tool
async def get_page(
    ctx: Context,
    page_id: Annotated[int, Field(description="The unique Productive page identifier")],
) -> Dict[str, Any]:
    """Get specific page/document details with full content.

    Returns:
        Dictionary with complete page details including JSON-formatted content
    """
    return await tools_read.get_page(ctx, page_id)


@mcp.tool
async def get_people(
    ctx: Context,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of people per page (max 200)")
    ] = None,
) -> Dict[str, Any]:
    """Get all team members/people with optional pagination.

    Returns team member data including:
    - Person ID, name, and email
    - Role and title information
    - Last seen and join dates
    - Avatar and contact information
    """
    return await tools_read.get_people(
        ctx,
        page_number=page_number,
        page_size=page_size,
    )


@mcp.tool
async def get_person(
    ctx: Context,
    person_id: Annotated[int, Field(description="The unique Productive person identifier")],
) -> Dict[str, Any]:
    """Get detailed information about a specific team member/person.

    Returns comprehensive person details including:
    - Full name, email, and contact information
    - Role, title, and organizational details
    - Activity timestamps (joined, last seen)
    - Custom fields and additional metadata
    - Avatar and profile information
    """
    return await tools_read.get_person(ctx, person_id)


@mcp.tool
async def get_attachments(
    ctx: Context,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of attachments per page (max 200)")
    ] = None,
    extra_filters: Annotated[
        dict, Field(description="Additional Productive query filters using API syntax")
    ] = None,
) -> Dict[str, Any]:
    """Get all attachments/files with optional filtering.

    Attachments are files (PDFs, images, documents) that can be associated with
    various Productive entities like tasks, comments, expenses, etc.

    Returns:
        Dictionary containing attachment metadata (name, type, size, relationships)
        Note: This provides metadata only, not actual file content
    """
    return await tools_read.get_attachments(
        ctx, page_number=page_number, page_size=page_size, extra_filters=extra_filters
    )


@mcp.tool
async def create_page(
    ctx: Context,
    title: Annotated[str, Field(description="Page title")],
    project_id: Annotated[int, Field(description="Project ID where the page will be created")],
    body: Annotated[str, Field(description="Page content/body (supports HTML/markdown)")] = "",
    parent_page_id: Annotated[int, Field(description="Optional parent page ID for nested pages")] = None,
) -> Dict[str, Any]:
    """Create a new page in a project.

    Pages in Productive are documents that can contain rich text content,
    attachments, and are organized within projects. Pages can be nested
    by specifying a parent_page_id.

    Returns:
        Dictionary with the created page details including:
        - Page ID, title, and body
        - Project and parent page relationships
        - Creation timestamps and author information
        - Webapp URL for direct access

    Examples:
        create_page("Meeting Notes", 12345, "# Notes from today's meeting...")
        create_page("Sub-page", 12345, "Content", parent_page_id=67890)
    """
    return await tools_write.create_page(
        ctx,
        title=title,
        project_id=project_id,
        body=body,
        parent_page_id=parent_page_id,
    )


@mcp.tool
async def update_page(
    ctx: Context,
    page_id: Annotated[int, Field(description="The unique Productive page identifier")],
    title: Annotated[str, Field(description="Optional new page title")] = None,
    body: Annotated[str, Field(description="Optional new page content/body")] = None,
) -> Dict[str, Any]:
    """Update an existing page.

    Allows partial updates - only provide the fields you want to change.
    If both title and body are omitted, no changes will be made.

    Returns:
        Dictionary with the updated page details including:
        - Updated page ID, title, and body
        - Modification timestamps
        - Webapp URL for direct access

    Examples:
        update_page(12345, title="Updated Title")
        update_page(12345, body="New content")
        update_page(12345, title="New Title", body="New content")
    """
    return await tools_write.update_page(
        ctx,
        page_id=page_id,
        title=title,
        body=body,
    )


if __name__ == "__main__":
    mcp.run()
