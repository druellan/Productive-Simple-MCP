"""
Simple MCP server to access the Productive API.

This software is provided "as is" without warranty of any kind. Use at your own risk.
Author: druellan (druellan@ecimtech.com)
License: MIT
"""

import json

from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from typing import Any, Dict, Annotated, Optional
from pydantic import Field
from config import config
from productive_client import client
import tools
from contextlib import asynccontextmanager
from toon import encode as toon_encode


@asynccontextmanager
async def lifespan(server):
    """Server lifespan context manager"""
    try:
        config.validate()
    except ValueError as e:
        raise ValueError(f"Configuration error: {str(e)}")

    yield

    await client.close()


class OutputSerializationMiddleware(Middleware):
    """Serialize tool output based on OUTPUT_FORMAT configuration.

    Intercepts tool results and serializes them to TOON or JSON format.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        result = await call_next(context)

        if result and hasattr(result, "content"):
            for item in result.content:
                if hasattr(item, "text"):
                    text = item.text
                    if text and isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                            if config.output_format == "toon":
                                try:
                                    item.text = toon_encode(parsed)
                                except Exception:
                                    pass
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

        return result


mcp = FastMCP(
    name="Productive MCP Server",
    instructions=(
        "Access Productive.io data: projects, folders, tasks, pages, comments, todos, people, workflow statuses, and time entries."
        "Use quick_search for general queries, get_recent_activity for team updates, get_task for specific tasks."
        "Use get_task_history for comprehensive task history including status changes, assignments, and milestones."
        "Use get_people to list team members and get_person for individual details."
        "All endpoints paginate (max 200 items). Use filters when possible to reduce scope."
    ),
    version="1.0.0 RC1",
    lifespan=lifespan,
    on_duplicate="warn",
)

mcp.add_middleware(OutputSerializationMiddleware())


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
    return await tools.quick_search(
        ctx,
        query=query,
        search_types=search_types,
        deep_search=deep_search,
        page=page,
        per_page=per_page,
    )


@mcp.tool
async def list_recent_activity(
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
        list_recent_activity()  # Last 24 hours, all activity
        list_recent_activity(hours=168)  # Last week
        list_recent_activity(hours=48, project_id=343136)  # Last 2 days on specific project
        list_recent_activity(hours=24, user_id=12345)  # What a specific user did today
        list_recent_activity(hours=24, activity_type=1)  # Only comments from last day
        list_recent_activity(hours=168, item_type='Task')  # Task activities from last week
        list_recent_activity(hours=168, event_type='edit')  # Task edits from last week
        list_tasks(extra_filters={'filter[status][eq]': 2}, sort='-updated_at', page_size=10)  # Recently closed tasks
    """
    return await tools.list_recent_activity(
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
async def list_projects(ctx: Context) -> Dict[str, Any]:
    """List all projects with basic information.

    Returns project data including:
    - Project ID, name, and number
    - Creation and last activity timestamps
    - Archived status (if applicable)
    - Webapp URL for direct access
    """
    return await tools.list_projects(ctx)


@mcp.tool
async def list_folders(
    ctx: Context,
    project_id: Annotated[
        int, Field(description="Productive project ID to list folders for")
    ],
    status: Annotated[
        int,
        Field(description="Folder status filter: 1 = active, 2 = archived"),
    ] = 1,
    limit: Annotated[
        int, Field(description="Maximum number of folders to return (max 200)")
    ] = config.items_per_page,
) -> Dict[str, Any]:
    """List folders in a project.

    Productive exposes folders through the `/folders` endpoint.

    Returns folder data including:
    - Folder ID and name
    - Archived status
    - Position/order within the project
    - Hidden flag and project relationship
    """
    return await tools.list_folders(
        ctx,
        project_id=project_id,
        status=status,
        limit=limit,
    )


@mcp.tool
async def get_folder(
    ctx: Context,
    folder_id: Annotated[int, Field(description="Productive folder ID")],
) -> Dict[str, Any]:
    """Get folder details by folder ID.

    Productive exposes folders through the `/folders` endpoint.
    """
    return await tools.get_folder(ctx, folder_id)


@mcp.tool
async def list_workflow_statuses(
    ctx: Context,
    workflow_id: Annotated[
        int, Field(description="Optional workflow ID to filter statuses")
    ] = None,
    category_id: Annotated[
        int,
        Field(description="Optional category filter: 1 = Not Started, 2 = Started, 3 = Closed"),
    ] = None,
    limit: Annotated[
        int, Field(description="Maximum number of workflow statuses to return (max 200)")
    ] = config.items_per_page,
) -> Dict[str, Any]:
    """List workflow statuses from Productive.

    Useful for understanding valid task status values by workflow.
    """
    return await tools.list_workflow_statuses(
        ctx,
        workflow_id=workflow_id,
        category_id=category_id,
        limit=limit,
    )


@mcp.tool
async def list_time_entries(
    ctx: Context,
    date: Annotated[str, Field(description="Optional date filter (YYYY-MM-DD)")] = None,
    after: Annotated[str, Field(description="Optional lower bound date filter (YYYY-MM-DD)")] = None,
    before: Annotated[str, Field(description="Optional upper bound date filter (YYYY-MM-DD)")] = None,
    person_id: Annotated[int, Field(description="Optional person ID filter")] = None,
    project_id: Annotated[int, Field(description="Optional project ID filter")] = None,
    task_id: Annotated[int, Field(description="Optional task ID filter")] = None,
    service_id: Annotated[int, Field(description="Optional service ID filter")] = None,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    limit: Annotated[int, Field(description="Maximum number of time entries to return (max 200)")] = config.items_per_page,
) -> Dict[str, Any]:
    """List time entries with optional date and relationship filters.

    Returns logged work records and related references (person/service/task).
    """
    return await tools.list_time_entries(
        ctx,
        date=date,
        after=after,
        before=before,
        person_id=person_id,
        project_id=project_id,
        task_id=task_id,
        service_id=service_id,
        page_number=page_number,
        limit=limit,
    )


@mcp.tool
async def list_tasks(
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
    """List tasks with optional filtering and pagination.

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
    return await tools.list_tasks(
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
    """Get detailed task information by its internal task ID (e.g., 14677418).

    Returns task details including:
    - Title, description, status (open/closed), due date, and timestamps
    - Time tracking: initial estimate, remaining, billable, and worked time (in minutes)
    - Todo counts: total and open
    """
    return await tools.get_task(ctx=ctx, task_id=task_id)


async def create_task(
    ctx: Context,
    title: Annotated[str, Field(description="Task title")],
    project_id: Annotated[int, Field(description="Productive project ID where the task will be created")],
    description: Annotated[str, Field(description="Optional task description")] = None,
    board_id: Annotated[int, Field(description="Optional board ID")] = None,
    task_list_id: Annotated[int, Field(description="Optional task list ID")] = None,
    assignee_id: Annotated[int, Field(description="Optional assignee (person) ID")] = None,
    due_date: Annotated[str, Field(description="Optional due date (YYYY-MM-DD)")] = None,
    status: Annotated[str, Field(description="Task status: 'open' or 'closed'")] = "open",
) -> Dict[str, Any]:
    """Create a new task in a Productive project.

    Accepts title and project ID (required), plus optional description, board/task list
    assignment, assignee, and due date. Returns the created task object with full details.

    Examples:
        create_task(title="Fix login bug", project_id=12345)
        create_task(title="Review PR", project_id=123, assignee_id=999, due_date="2026-04-25")
    """
    return await tools.create_task(
        ctx=ctx,
        title=title,
        project_id=project_id,
        description=description,
        board_id=board_id,
        task_list_id=task_list_id,
        assignee_id=assignee_id,
        due_date=due_date,
        status=status,
    )


async def update_task(
    ctx: Context,
    task_id: Annotated[int, Field(description="Productive task ID to update")],
    title: Annotated[str, Field(description="New task title")] = None,
    description: Annotated[str, Field(description="New task description")] = None,
    assignee_id: Annotated[
        int,
        Field(
            description="New assignee person ID. Use 0 or negative to unassign the task."
        ),
    ] = None,
    due_date: Annotated[str, Field(description="New due date (YYYY-MM-DD)")] = None,
    status: Annotated[str, Field(description="New status: 'open' or 'closed'")] = None,
    board_id: Annotated[int, Field(description="Move task to this board")] = None,
    task_list_id: Annotated[
        int, Field(description="Move task to this task list")
    ] = None,
) -> Dict[str, Any]:
    """Update an existing task in Productive.

    Only provided fields are modified (partial PATCH). At least one field must be given.
    Supports updating title, description, assignee, due date, status, board, and task list
    in a single call. To unassign a task, pass assignee_id as 0 or a negative number.

    Examples:
        update_task(task_id=14677921, title="Updated title")
        update_task(task_id=14677921, status="closed", assignee_id=0)
        update_task(task_id=14677921, due_date="2026-05-01", board_id=456)
    """
    return await tools.update_task(
        ctx=ctx,
        task_id=task_id,
        title=title,
        description=description,
        assignee_id=assignee_id,
        due_date=due_date,
        status=status,
        board_id=board_id,
        task_list_id=task_list_id,
    )


async def delete_task(
    ctx: Context,
    task_id: Annotated[int, Field(description="Productive task ID to delete")],
) -> Dict[str, Any]:
    """Permanently delete a task from Productive by its ID.

    This action is irreversible — the task and all associated data (comments, todos,
    time entries) will be removed. Use with caution.

    Examples:
        delete_task(task_id=14677921)
    """
    return await tools.delete_task(ctx=ctx, task_id=task_id)


async def create_comment(
    ctx: Context,
    body: Annotated[str, Field(description="Comment body text (HTML supported)")],
    task_id: Annotated[
        Optional[int],
        Field(description="Productive task ID to attach the comment to"),
    ] = None,
    project_id: Annotated[
        Optional[int],
        Field(description="Productive project ID to attach the comment to"),
    ] = None,
) -> Dict[str, Any]:
    """Create a new comment on a task or project in Productive.

    At least one of task_id or project_id must be provided. The comment body
    supports HTML formatting.

    Examples:
        create_comment(body="Great work on this!", task_id=14677921)
        create_comment(body="<p>Updated status</p>", project_id=343136)
        create_comment(body="Closing note", task_id=14677921, project_id=343136)
    """
    return await tools.create_comment(
        ctx=ctx, body=body, task_id=task_id, project_id=project_id
    )


async def update_comment(
    ctx: Context,
    comment_id: Annotated[int, Field(description="Productive comment ID to update")],
    body: Annotated[str, Field(description="New comment body text (HTML supported)")],
) -> Dict[str, Any]:
    """Update the body of an existing comment in Productive.

    Only the body attribute can be modified on comments.

    Examples:
        update_comment(comment_id=98765, body="Updated comment text")
        update_comment(comment_id=98765, body="<p>Revised <strong>note</strong></p>")
    """
    return await tools.update_comment(ctx=ctx, comment_id=comment_id, body=body)


async def delete_comment(
    ctx: Context,
    comment_id: Annotated[int, Field(description="Productive comment ID to delete")],
) -> Dict[str, Any]:
    """Permanently delete a comment from Productive by its ID.

    This action is irreversible — the comment will be removed from the task or project.

    Examples:
        delete_comment(comment_id=98765)
    """
    return await tools.delete_comment(ctx=ctx, comment_id=comment_id)


async def create_time_entry(
    ctx: Context,
    date: Annotated[str, Field(description="Date for the time entry (YYYY-MM-DD)")],
    time: Annotated[float, Field(description="Time spent in hours (e.g., 2.5 for 2.5 hours)")],
    person_id: Annotated[int, Field(description="Person ID who logged the time")],
    task_id: Annotated[int, Field(description="Task ID to associate the time entry with")] = None,
    service_id: Annotated[int, Field(description="Service ID to associate the time entry with")] = None,
    note: Annotated[str, Field(description="Optional note or description")] = None,
) -> Dict[str, Any]:
    """Create a new time entry for time tracking in Productive.

    Logs time spent on tasks or services. Either task_id or service_id must be provided.

    Examples:
        create_time_entry(date="2026-04-24", time=2.5, person_id=123, task_id=456)
        create_time_entry(date="2026-04-24", time=1.0, person_id=123, service_id=789, note="Code review")
    """
    return await tools.create_time_entry(
        ctx=ctx,
        date=date,
        time=time,
        person_id=person_id,
        task_id=task_id,
        service_id=service_id,
        note=note,
    )


async def update_time_entry(
    ctx: Context,
    time_entry_id: Annotated[int, Field(description="Productive time entry ID to update")],
    date: Annotated[str, Field(description="New date (YYYY-MM-DD)")] = None,
    time: Annotated[float, Field(description="New time in hours")] = None,
    person_id: Annotated[int, Field(description="New person ID")] = None,
    task_id: Annotated[int, Field(description="New task ID")] = None,
    service_id: Annotated[int, Field(description="New service ID")] = None,
    note: Annotated[str, Field(description="New note")] = None,
) -> Dict[str, Any]:
    """Update an existing time entry in Productive.

    Only provided fields are modified (partial PATCH). At least one field must be given.

    Examples:
        update_time_entry(time_entry_id=12345, time=3.0)
        update_time_entry(time_entry_id=12345, date="2026-04-25", note="Updated description")
    """
    return await tools.update_time_entry(
        ctx=ctx,
        time_entry_id=time_entry_id,
        date=date,
        time=time,
        person_id=person_id,
        task_id=task_id,
        service_id=service_id,
        note=note,
    )


async def delete_time_entry(
    ctx: Context,
    time_entry_id: Annotated[int, Field(description="Productive time entry ID to delete")],
) -> Dict[str, Any]:
    """Permanently delete a time entry from Productive by its ID.

    This action is irreversible — the time entry will be removed from time tracking records.

    Examples:
        delete_time_entry(time_entry_id=12345)
    """
    return await tools.delete_time_entry(ctx=ctx, time_entry_id=time_entry_id)


async def create_page(
    ctx: Context,
    title: Annotated[str, Field(description="Page title")],
    project_id: Annotated[int, Field(description="Productive project ID where the page will be created")],
    content: Annotated[str, Field(description="Optional page content (supports HTML)")] = None,
) -> Dict[str, Any]:
    """Create a new page/document in a Productive project.

    Pages are documents that can contain rich text content and are organized within projects.

    Examples:
        create_page(title="Meeting Notes", project_id=12345)
        create_page(title="Project Plan", project_id=12345, content="<h1>Project Overview</h1><p>Details...</p>")
    """
    return await tools.create_page(
        ctx=ctx,
        title=title,
        project_id=project_id,
        content=content,
    )


async def update_page(
    ctx: Context,
    page_id: Annotated[int, Field(description="Productive page ID to update")],
    title: Annotated[str, Field(description="New page title")] = None,
    content: Annotated[str, Field(description="New page content (HTML supported)")] = None,
) -> Dict[str, Any]:
    """Update an existing page/document in Productive.

    Only provided fields are modified (partial PATCH). At least one field must be given.

    Examples:
        update_page(page_id=67890, title="Updated Meeting Notes")
        update_page(page_id=67890, content="<h1>Revised Notes</h1><p>New content...</p>")
    """
    return await tools.update_page(
        ctx=ctx,
        page_id=page_id,
        title=title,
        content=content,
    )


async def delete_page(
    ctx: Context,
    page_id: Annotated[int, Field(description="Productive page ID to delete")],
) -> Dict[str, Any]:
    """Permanently delete a page/document from Productive by its ID.

    This action is irreversible — the page and all its content will be removed.

    Examples:
        delete_page(page_id=67890)
    """
    return await tools.delete_page(ctx=ctx, page_id=page_id)


async def create_todo(
    ctx: Context,
    content: Annotated[str, Field(description="Todo item content/description")],
    task_id: Annotated[int, Field(description="Productive task ID to add the todo to")],
) -> Dict[str, Any]:
    """Create a new todo checklist item for a task in Productive.

    Todos are checkbox items within tasks for granular tracking of work items.

    Examples:
        create_todo(content="Write unit tests", task_id=14677921)
        create_todo(content="Update documentation", task_id=14677921)
    """
    return await tools.create_todo(
        ctx=ctx,
        content=content,
        task_id=task_id,
    )


async def update_todo(
    ctx: Context,
    todo_id: Annotated[int, Field(description="Productive todo ID to update")],
    content: Annotated[str, Field(description="New todo content")] = None,
    completed: Annotated[bool, Field(description="Mark todo as completed (true) or incomplete (false)")] = None,
) -> Dict[str, Any]:
    """Update an existing todo checklist item in Productive.

    Only provided fields are modified (partial PATCH). At least one field must be given.

    Examples:
        update_todo(todo_id=11111, content="Revised item description")
        update_todo(todo_id=11111, completed=True)
    """
    return await tools.update_todo(
        ctx=ctx,
        todo_id=todo_id,
        content=content,
        completed=completed,
    )


async def delete_todo(
    ctx: Context,
    todo_id: Annotated[int, Field(description="Productive todo ID to delete")],
) -> Dict[str, Any]:
    """Permanently delete a todo checklist item from Productive by its ID.

    This action is irreversible — the todo item will be removed from the task.

    Examples:
        delete_todo(todo_id=11111)
    """
    return await tools.delete_todo(ctx=ctx, todo_id=todo_id)


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
            le=8760,  # 1 year max
        ),
    ] = 720,
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
        get_task_history(14677921, hours=24)  # Last 24 hours
    """
    return await tools.get_task_history(ctx, task_id, hours)


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
async def list_comments(
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
    """List comments with optional filtering by project or task.

    Returns:
    - Comment text, author, and timestamp
    - Parent entity (project or task) with details
    - Discussion threads and replies
    - Attachments and file references
    - Mentions of team members or clients

    Use extra_filters with filter[discussion_id][eq] to target a specific thread.
    """
    return await tools.list_comments(
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
async def list_todos(
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
    """List todo checklist items with optional filtering by task.

    Returns:
    - Checkbox item text and completion status
    - Assignee information
    - Parent task details with project context
    - Due dates and priority relative to parent task
    - Estimated vs actual time for checklist items

    Filter by task_id to get all checklist items for a specific task.
    """
    return await tools.list_todos(
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
    """Get a specific todo checklist item by ID.

    Returns:
    - Checkbox item text and completion status
    - Parent task with project and client details
    - Assignee and team member information
    - Due date relative to parent task timeline
    - Time estimates vs actual completion time
    - Related comments and file attachments
    """
    return await tools.get_todo(ctx, todo_id)


@mcp.tool
async def list_pages(
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
    """List pages/documents with optional filtering by project or creator.

    Pages in Productive are documents that can contain rich text content,
    attachments, and are organized within projects.

    Returns page titles, content, metadata, and project relationships.

    Examples:
        list_pages(project_id=1234)  # All pages in a project
        list_pages(creator_id=567)   # Pages created by a specific person
    """
    return await tools.list_pages(
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
    """Get a specific page/document by ID, including full content body."""
    return await tools.get_page(ctx, page_id)


@mcp.tool
async def list_people(
    ctx: Context,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of people per page (max 200)")
    ] = None,
) -> Dict[str, Any]:
    """List all team members with optional pagination.

    Returns:
    - Person ID, name, and email
    - Role and title information
    - Last seen and join dates
    - Avatar and contact information
    """
    return await tools.list_people(
        ctx,
        page_number=page_number,
        page_size=page_size,
    )


@mcp.tool
async def get_person(
    ctx: Context,
    person_id: Annotated[
        int, Field(description="The unique Productive person identifier")
    ],
) -> Dict[str, Any]:
    """Get detailed information about a specific team member by ID.

    Returns:
    - Full name, email, and contact information
    - Role, title, and organizational details
    - Activity timestamps (joined, last seen)
    - Custom fields and additional metadata
    - Avatar and profile information
    """
    return await tools.get_person(ctx, person_id)


@mcp.tool
async def list_attachments(
    ctx: Context,
    page_number: Annotated[int, Field(description="Page number for pagination")] = None,
    page_size: Annotated[
        int, Field(description="Optional number of attachments per page (max 200)")
    ] = None,
    extra_filters: Annotated[
        dict, Field(description="Additional Productive query filters using API syntax")
    ] = None,
) -> Dict[str, Any]:
    """List attachment/file metadata with optional filtering.

    Attachments are files (PDFs, images, documents) associated with tasks, comments, expenses, etc.

    Returns:
    - File name, type, and size
    - Associated entity relationships (task, project, etc.)

    Note: returns metadata only — actual file content is not included.
    """
    return await tools.list_attachments(
        ctx, page_number=page_number, page_size=page_size, extra_filters=extra_filters
    )


if not config.read_only:
    for _write_tool in [
        create_task,
        update_task,
        delete_task,
        create_comment,
        update_comment,
        delete_comment,
        create_time_entry,
        update_time_entry,
        delete_time_entry,
        create_page,
        update_page,
        delete_page,
        create_todo,
        update_todo,
        delete_todo,
    ]:
        mcp.tool(_write_tool)


def main() -> None:
    """Run the MCP server using the configured default transport."""
    mcp.run()


if __name__ == "__main__":
    main()
