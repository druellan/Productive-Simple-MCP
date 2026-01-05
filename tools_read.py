from fastmcp import Context
from fastmcp.tools.tool import ToolResult

from config import config
from productive_client import client, ProductiveAPIError
from utils import filter_response, filter_task_list_response, filter_page_list_response, _handle_productive_api_error


async def get_projects(ctx: Context) -> ToolResult:
    """Fetch projects and post-process response for LLM safety.

    - Wraps client.get_projects(); sorts by most recent activity first.
    - Applies utils.filter_response to strip noise and add webapp_url.
    - Raises ProductiveAPIError on API failure; errors are logged via ctx.
    """
    try:
        await ctx.info("Fetching all projects")
        params = {"sort": "-last_activity_at"}
        result = await client.get_projects(params=params)
        await ctx.info("Successfully retrieved projects")
        filtered = filter_response(result)

        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "projects")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching projects: {str(e)}")
        raise e


async def get_tasks(
    ctx: Context,
    page_number: int = None,
    page_size: int = config.items_per_page,
    sort: str = "-last_activity_at",
    project_id: int = None,
    user_id: int = None,
    extra_filters: dict = None
) -> ToolResult:
    """
    List tasks with optional filters and pagination.

    - project_id and user_id are converted to Productive API filters.
    - extra_filters is passed through directly to the API (e.g., filter[status][eq]).
    - Enforces a configurable default page[size] for consistency when not provided.
    - Sort supports Productive's allowed fields (e.g., last_activity_at, created_at, due_date).
    - Response is cleaned with utils.filter_task_list_response (excludes descriptions for lean lists).
    """
    try:
        await ctx.info("Fetching tasks")
        params = {}
        if page_number is not None:
            params["page[number]"] = page_number
        params["page[size]"] = page_size
        if sort:
            params["sort"] = sort
        if project_id is not None:
            params["filter[project_id][eq]"] = project_id
        if user_id is not None:
            params["filter[assignee_id][eq]"] = user_id
        if extra_filters:
            params.update(extra_filters)

        result = await client.get_tasks(params=params if params else None)
        await ctx.info("Successfully retrieved tasks")

        filtered = filter_task_list_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "tasks")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching tasks: {str(e)}")
        raise e


async def get_task(ctx: Context, task_id: int) -> ToolResult:
    """Fetch a single task by internal ID.

    - Wraps client.get_task(task_id).
    - Applies utils.filter_response to sanitize output.
    - Ensures time tracking fields are always present (initial_estimate, worked_time, billable_time, remaining_time).
    - Raises ProductiveAPIError on failure.
    """
    try:
        await ctx.info(f"Fetching task with ID: {task_id}")
        result = await client.get_task(task_id)
        await ctx.info("Successfully retrieved task")
        
        filtered = filter_response(result)
        
        # Ensure time tracking fields are always present at the top level
        if "data" in filtered and "attributes" in filtered["data"]:
            attributes = filtered["data"]["attributes"]
            
            # Set default values for time tracking fields if missing
            time_fields = {
                "initial_estimate": 0,
                "worked_time": 0,
                "billable_time": 0,
                "remaining_time": 0
            }
            
            for field, default_value in time_fields.items():
                if field not in attributes or attributes[field] is None:
                    attributes[field] = default_value
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"task {task_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching task: {str(e)}")
        raise e


async def get_project_tasks(
    ctx: Context,
    project_id: int,
    status: int = None
) -> ToolResult:
    """List tasks for a project with an optional status filter.

    - status expects integers per Productive: 1=open, 2=closed (mapped to filter[status][eq]).
    - Sorts by most recent activity first.
    - Uses configurable page[size] for consistency.
    - Applies utils.filter_task_list_response (lighter payload than filter_response).
    - On 404/empty, returns an empty data array with an informational meta message.
    """
    try:
        await ctx.info(f"Fetching all tasks for project {project_id}")
        
        # Get all tasks for the project with a high limit
        params = {
            "filter[project_id][eq]": project_id,
            "page[size]": config.items_per_page  # Configurable limit for comprehensive view
        }
        
        # Status filter: 1 = open, 2 = closed (per Productive API docs)
        if status is not None:
            params["filter[status][eq]"] = status
        
        params["sort"] = "-last_activity_at"
        
        result = await client.get_tasks(params=params)
        
        if not result.get("data") or len(result["data"]) == 0:
            await ctx.info(f"No tasks found for project {project_id}")
            return {"data": [], "meta": {"message": f"No tasks found for project {project_id}"}}
        
        # Use lighter filtering for task lists - removes descriptions and relationships
        filtered = filter_task_list_response(result)
        await ctx.info(f"Successfully retrieved {len(result['data'])} tasks for project {project_id}")
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"tasks for project {project_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching tasks: {str(e)}")
        raise e


async def get_project_task(
    ctx: Context,
    task_number: str,
    project_id: int
) -> ToolResult:
    """Fetch a task by its project-scoped task_number.

    - Uses filter[project_id][eq] and filter[task_number][eq].
    - Returns the first matched record (API constrained to one).
    - Raises ProductiveAPIError(404) if not found.
    """
    try:
        await ctx.info(f"Fetching task #{task_number} from project {project_id}")
        
        # Get tasks for the project filtered by task_number
        params = {
            "filter[project_id][eq]": project_id,
            "filter[task_number][eq]": task_number
        }
        
        result = await client.get_tasks(params=params)
        
        if not result.get("data") or len(result["data"]) == 0:
            raise ProductiveAPIError(
                message=f"Task #{task_number} not found in project {project_id}",
                status_code=404
            )
        
        # Return the first (and should be only) task
        task_data = result["data"][0]
        filtered = filter_response({"data": task_data})
        await ctx.info(f"Successfully retrieved task #{task_number}")
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"task #{task_number}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching task: {str(e)}")
        raise e


async def get_comments(
    ctx: Context,
    project_id: int = None,
    task_id: int = None,
    page_number: int = None,
    page_size: int = config.items_per_page,
    extra_filters: dict = None
) -> ToolResult:
    """List comments with optional filters and pagination.

    - Pass-through for extra_filters (e.g., discussion_id, page_id, task_id).
    - Enforces configurable default page[size] if not provided.
    - Sort defaults to "-created_at" (most recent first).
    - Applies utils.filter_response to sanitize.
    - Uses consistent scalar filters: filter[project_id][eq], filter[task_id][eq]
    """
    try:
        await ctx.info("Fetching comments")
        params = {}
        if page_number is not None:
            params["page[number]"] = page_number
        params["page[size]"] = page_size
        if project_id is not None:
            params["filter[project_id][eq]"] = project_id
        if task_id is not None:
            params["filter[task_id][eq]"] = task_id
        if extra_filters:
            params.update(extra_filters)

        # Add default sorting
        params["sort"] = "-created_at"

        result = await client.get_comments(params=params if params else None)
        await ctx.info("Successfully retrieved comments")

        filtered = filter_response(result)

        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "comments")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching comments: {str(e)}")
        raise e


async def get_comment(ctx: Context, comment_id: int) -> ToolResult:
    """Fetch a single comment by ID and sanitize the response."""
    try:
        await ctx.info(f"Fetching comment with ID: {comment_id}")
        result = await client.get_comment(comment_id)
        await ctx.info("Successfully retrieved comment")
        
        filtered = filter_response(result)
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"comment {comment_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching comment: {str(e)}")
        raise e


async def get_todos(
    ctx: Context,
    task_id: int = None,
    page_number: int = None,
    page_size: int = config.items_per_page,
    extra_filters: dict = None
) -> ToolResult:
    """List todo checklist items with optional filters.

    - task_id is an int; API expects filter[task_id] to be array or scalar; we send scalar.
    - Enforces configurable default page[size] when not provided.
    - Use extra_filters for status ints (1=open, 2=closed) or assignee filters.
    - Sorting not supported by API - uses default order.
    - Applies utils.filter_response.
    """
    try:
        await ctx.info("Fetching todos")
        params = {}
        if page_number is not None:
            params["page[number]"] = page_number
        params["page[size]"] = page_size
        if task_id is not None:
            params["filter[task_id]"] = [task_id]
        if extra_filters:
            params.update(extra_filters)

        result = await client.get_todos(params=params if params else None)
        await ctx.info("Successfully retrieved todos")
        
        filtered = filter_response(result)
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "todos")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching todos: {str(e)}")
        raise e


async def get_todo(ctx: Context, todo_id: int) -> ToolResult:
    """Fetch a single todo by ID and sanitize the response."""
    try:
        await ctx.info(f"Fetching todo with ID: {todo_id}")
        result = await client.get_todo(todo_id)
        await ctx.info("Successfully retrieved todo")
        
        filtered = filter_response(result)
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"todo {todo_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching todo: {str(e)}")
        raise e


async def get_recent_activity(
    ctx: Context,
    hours: int = 24,
    user_id: int = None,
    project_id: int = None,
    activity_type: int = None,
    item_type: str = None,
    event_type: str = None,
    task_id: int = None,
    max_results: int = None
) -> ToolResult:
    """Summarize recent activities within a time window.

    - Builds filter[after] from UTC now minus `hours`.
    - Optional filters map directly: person_id, project_id, type (1:Comment,2:Changeset,3:Email), item_type, event, task_id.
    - Respects API page[size] limit (<=200) via max_results.
    - Response is sanitized and meta is enriched with basic counts via _summarize_activities.
    - Avoids unsupported sorts on /activities.
    """
    try:
        from datetime import datetime, timedelta

        if max_results is None:
            max_results = config.items_per_page

        # Validate max_results
        if max_results > 200:
            await ctx.warning("max_results exceeds API limit of 200, using 200")
            max_results = 200
        
        # Calculate the cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        after_date = cutoff_time.isoformat() + "Z"
        
        await ctx.info(f"Fetching activities from the last {hours} hours")
        
        # Build comprehensive filter params
        params = {
            "filter[after]": after_date,
            "page[size]": max_results
        }
        
        # Apply optional filters
        if user_id:
            params["filter[person_id]"] = user_id
            
        if project_id:
            params["filter[project_id]"] = project_id
            
        if activity_type:
            params["filter[type]"] = activity_type
            
        if item_type:
            params["filter[item_type]"] = item_type
            
        if event_type:
            params["filter[event]"] = event_type
            
        if task_id:
            params["filter[task_id]"] = task_id
        
        result = await client.get_activities(params=params)
        
        if not result.get("data") or len(result["data"]) == 0:
            await ctx.info("No recent activities found")
            return {
                "data": [],
                "meta": {
                    "message": f"No activities found in the last {hours} hours",
                    "hours": hours,
                    "filters_applied": _get_applied_filters(params),
                    "cutoff_time": after_date
                }
            }
        
        filtered = filter_response(result)
        
        # Enhance metadata with activity summary
        activity_summary = _summarize_activities(filtered.get("data", []))
        filtered["meta"] = filtered.get("meta", {})
        filtered["meta"].update({
            "activity_summary": activity_summary,
            "total_activities": len(filtered.get("data", [])),
            "filters_applied": _get_applied_filters(params),
            "cutoff_time": after_date
        })
        
        await ctx.info(f"Successfully retrieved {len(result['data'])} recent activities")
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "activities")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching recent updates: {str(e)}")
        raise e


def _get_applied_filters(params: dict) -> dict:
    """Extract and format the filters that were actually applied."""
    applied_filters = {}
    
    # Remove pagination and standard params
    filter_params = {k: v for k, v in params.items() if k.startswith("filter[")}
    
    for key, value in filter_params.items():
        # Extract filter name from key like "filter[person_id]"
        filter_name = key.replace("filter[", "").replace("]", "")
        applied_filters[filter_name] = value
    
    return applied_filters


async def get_task_history(
    ctx: Context,
    task_id: int,
    hours: int = 720  # Default to 30 days for comprehensive history
) -> ToolResult:
    """Get comprehensive history for a specific task.

    - Aggregates historical data from activities and task events
    - Returns status history, assignment history, milestones, and activity summary
    - Ignores unavailable data gracefully (empty arrays/null values)
    - Uses get_recent_activity with task_id filter for historical data
    - Now extracts status transitions from changeset (workflow_status_id)
    """
    try:
        # Get the task details first to verify it exists
        await ctx.info(f"Fetching history for task {task_id}")
        task_result = await get_task(ctx, task_id)

        if not task_result.get("data"):
            await ctx.error(f"Task {task_id} not found")
            return {
                "task_id": task_id,
                "error": "Task not found",
                "status_history": [],
                "assignment_history": [],
                "milestones": [],
                "activity_summary": {}
            }

        # Get recent activities for this task (comprehensive history)
        activity_result = await get_recent_activity(
            ctx,
            hours=hours,
            task_id=task_id,
            max_results=200  # Maximum allowed by API
        )

        activities = activity_result.get("data", [])

        # Parse activities to extract status changes, assignments, milestones
        status_history = []
        assignment_history = []
        milestones = []

        for activity in activities:
            attributes = activity.get("attributes", {})
            event_type = attributes.get("event")
            item_type = attributes.get("item_type")
            created_at = attributes.get("created_at")
            person_name = attributes.get("person_name", "Unknown")

            # Status changes (workflow_status_id in changeset)
            changeset = attributes.get("changeset", [])
            if item_type and item_type.lower() == "task" and event_type in ["update", "edit"]:
                for change in changeset:
                    if "workflow_status_id" in change:
                        status_from = change["workflow_status_id"][0]["value"] if len(change["workflow_status_id"]) > 0 else None
                        status_to = change["workflow_status_id"][1]["value"] if len(change["workflow_status_id"]) > 1 else None
                        status_history.append({
                            "from": status_from,
                            "to": status_to,
                            "changed_at": created_at
                        })

            # Assignment changes (parse assignee in changeset)
            if item_type and item_type.lower() == "task" and event_type in ["update", "edit"]:
                for change in changeset:
                    if "assignee" in change:
                        # The changeset shows the new assignee only
                        assignee_to = change["assignee"][0]["value"] if len(change["assignee"]) > 0 else None
                        assignment_history.append({
                            "assigned_to": assignee_to,
                            "changed_at": created_at
                        })

            # Milestones (comments with milestone keywords or custom fields)
            if item_type and item_type.lower() == "comment" and "milestone" in attributes.get("item_name", "").lower():
                milestones.append({
                    "milestone": attributes.get("item_name", "Milestone"),
                    "completed_at": created_at,
                    "completed_by": person_name
                })

        # Build activity summary
        activity_summary = {
            "total_activities": len(activities),
            "total_comments": len([a for a in activities if a.get("attributes", {}).get("item_type") == "Comment"]),
            "total_changes": len([a for a in activities if a.get("attributes", {}).get("item_type") == "Task"]),
            "total_status_changes": len(status_history),
            "total_assignments": len(assignment_history),
            "total_milestones": len(milestones)
        }

        # Build final history response
        history_response = {
            "task_id": task_id,
            "status_history": status_history,
            "assignment_history": assignment_history,
            "milestones": milestones,
            "activity_summary": activity_summary
        }

        await ctx.info(f"Successfully retrieved history for task {task_id}")
        return history_response

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"task history for {task_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching task history: {str(e)}")
        raise e


def _summarize_activities(activities: list) -> dict:
    """Create a summary of activities by type and event."""
    summary = {
        "by_type": {},
        "by_event": {},
        "by_item_type": {},
        "total": len(activities)
    }
    
    for activity in activities:
        if not isinstance(activity, dict):
            continue
            
        attributes = activity.get("attributes", {})
        activity_type = attributes.get("type")
        event_type = attributes.get("event")
        item_type = attributes.get("item_type")
        
        # Count by activity type
        if activity_type:
            summary["by_type"][activity_type] = summary["by_type"].get(activity_type, 0) + 1
            
        # Count by event type
        if event_type:
            summary["by_event"][event_type] = summary["by_event"].get(event_type, 0) + 1
            
        # Count by item type
        if item_type:
            summary["by_item_type"][item_type] = summary["by_item_type"].get(item_type, 0) + 1
    
    return summary


async def get_pages(
    ctx: Context,
    project_id: int = None,
    creator_id: int = None,
    page_number: int = None,
    page_size: int = config.items_per_page
) -> ToolResult:
    """List pages (docs) with optional filters and pagination.

    - Supports project_id and creator_id filters.
    - Enforces configurable default page[size] if not provided.
    - Sorts by most recent updates first.
    - Applies utils.filter_response to sanitize (body excluded via type='pages').
    - Uses consistent scalar filters: filter[project_id][eq], filter[creator_id][eq]
    """
    try:
        await ctx.info("Fetching pages")
        params = {}
        if page_number is not None:
            params["page[number]"] = page_number
        params["page[size]"] = page_size
        if project_id is not None:
            params["filter[project_id][eq]"] = project_id
        if creator_id is not None:
            params["filter[creator_id][eq]"] = creator_id
        params["sort"] = "-updated_at"
        result = await client.get_pages(params=params if params else None)
        await ctx.info("Successfully retrieved pages")
        
        # For lists, remove heavy fields like body explicitly
        filtered = filter_page_list_response(result)
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "pages")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching pages: {str(e)}")
        raise e


async def get_page(ctx: Context, page_id: int) -> ToolResult:
    """Fetch a single page by ID.


    - Body is JSON in attributes.body (caller may parse if needed).
    - Applies utils.filter_response to sanitize (body included via type='page').
    """
    try:
        await ctx.info(f"Fetching page with ID: {page_id}")
        result = await client.get_page(page_id)
        await ctx.info("Successfully retrieved page")
        
        filtered = filter_response(result)
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"page {page_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching page: {str(e)}")
        raise e


async def get_attachments(
    ctx: Context,
    page_number: int = None,
    page_size: int = config.items_per_page,
    extra_filters: dict = None
) -> ToolResult:
    """List attachments with optional filters and pagination (metadata only).

    - Enforces configurable default page[size] when not provided.
    - Sorting not supported by API - uses default order.
    """
    try:
        await ctx.info("Fetching attachments")
        params = {}
        if page_number is not None:
            params["page[number]"] = page_number
        params["page[size]"] = page_size
        if extra_filters:
            params.update(extra_filters)

        result = await client.get_attachments(params=params if params else None)
        await ctx.info("Successfully retrieved attachments")
        
        filtered = filter_response(result)
        
        return filtered
        
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "attachments")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching attachments: {str(e)}")
        raise e


async def get_attachment(ctx: Context, attachment_id: int) -> ToolResult:
    """Fetch a single attachment by ID (metadata only)."""
    try:
        await ctx.info(f"Fetching attachment with ID: {attachment_id}")
        result = await client.get_attachment(attachment_id)
        await ctx.info("Successfully retrieved attachment")

        filtered = filter_response(result)

        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"attachment {attachment_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching attachment: {str(e)}")


async def get_people(ctx: Context, page_number: int = None, page_size: int = config.items_per_page) -> ToolResult:
    """List all team members/people with optional pagination.

    - Supports pagination with configurable default page[size].
    - Sorts by most recent activity first.
    - Applies utils.filter_response to sanitize output.
    - Returns basic info for all team members (name, email, role, etc.).
    """
    try:
        await ctx.info("Fetching all people")
        params = {}
        if page_number is not None:
            params["page[number]"] = page_number
        params["page[size]"] = page_size
        params["sort"] = "-last_seen_at"

        result = await client.get_people(params=params if params else None)
        await ctx.info("Successfully retrieved people")

        filtered = filter_response(result)

        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "people")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching people: {str(e)}")
        raise e


async def get_person(ctx: Context, person_id: int) -> ToolResult:
    """Fetch a single person/team member by ID.

    - Wraps client.get_person(person_id).
    - Applies utils.filter_response to sanitize output.
    - Returns detailed information about a specific team member.
    """
    try:
        await ctx.info(f"Fetching person with ID: {person_id}")
        result = await client.get_person(person_id)
        await ctx.info("Successfully retrieved person")

        filtered = filter_response(result)

        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, f"person {person_id}")
    except Exception as e:
        await ctx.error(f"Unexpected error fetching person: {str(e)}")
        raise e


async def quick_search(
    ctx: Context,
    query: str,
    search_types: list[str] = None,
    deep_search: bool = True,
    page: int = 1,
    per_page: int = 50
) -> ToolResult:
    """Quick search across projects, tasks, pages, and actions.

    This tool provides fast, comprehensive search across all Productive content types
    including projects, tasks, pages, and actions. It's optimized for quick lookups
    and general search queries.

    Args:
        query: Search query string
        search_types: List of types to search (action, project, task, page).
                     Defaults to ["action", "project", "task", "page"] if not provided.
        deep_search: Whether to perform deep search (default: True)
        page: Page number for pagination (default: 1)
        per_page: Results per page (default: 50)

    Returns:
        Search results from Productive API including:
        - Matching projects, tasks, pages, and actions
        - Relevance scores and metadata
        - Full entity details for each match
    """
    try:
        # Set default search_types if not provided
        if search_types is None:
            search_types = ["action", "project", "task", "page"]

        await ctx.info(f"Quick search with query: '{query}'")

        # Call the quick search method
        result = await client.quick_search(
            query=query,
            search_types=search_types,
            deep_search=deep_search,
            page=page,
            per_page=per_page
        )

        await ctx.info(f"Successfully retrieved {len(result.get('data', []))} search results")

        # Filter results to include only essential fields
        filtered_data = []
        for item in result.get("data", []):
            attributes = item.get("attributes", {})
            record_type = attributes.get("record_type", "")
            record_id = attributes.get("record_id", "")
            
            # Construct webapp URL (use raw record_type/record_id path; task hydration adds exact URL later)
            webapp_url = f"https://app.productive.io/27956-lineout/{record_type}s/{record_id}"
            
            filtered_item = {
                "record_id": record_id,
                "record_type": record_type,
                "title": attributes.get("title", ""),
                "subtitle": attributes.get("subtitle", ""),
                "icon_url": attributes.get("icon_url"),
                "status": attributes.get("status", ""),
                "project_name": attributes.get("meta", {}).get("project_name", ""),
                "updated_at": attributes.get("updated_at", ""),
                "webapp_url": webapp_url
            }
            
            # For tasks, hydrate with full task details to expose workflow_status_name (custom status)
            if record_type == "task" and record_id:
                try:
                    task_details = await client.get_task(int(record_id))
                    filtered_task = filter_response(task_details)
                    task_data = filtered_task.get("data", {}) if isinstance(filtered_task, dict) else {}
                    task_attrs = task_data.get("attributes", {}) if isinstance(task_data, dict) else {}

                    workflow_status = task_attrs.get("workflow_status_name")
                    if workflow_status:
                        filtered_item["workflow_status_name"] = workflow_status

                    # Prefer canonical webapp URL from filtered task if present
                    if "webapp_url" in task_data:
                        filtered_item["webapp_url"] = task_data["webapp_url"]
                except Exception as task_error:
                    await ctx.warning(f"Could not fetch workflow status for task {record_id}: {str(task_error)}")
            
            filtered_data.append(filtered_item)

        return {
            "data": filtered_data,
            "meta": {
                "query": query,
                "search_types": search_types,
                "deep_search": deep_search,
                "page": page,
                "per_page": per_page,
                "total_results": len(filtered_data)
            }
        }

    except ProductiveAPIError as e:
        await ctx.error(f"Quick search failed: {e.message}")
        return {
            "data": [],
            "meta": {
                "error": str(e),
                "status_code": e.status_code,
                "query": query
            }
        }
    except Exception as e:
        await ctx.error(f"Unexpected error during quick search: {str(e)}")
        return {
            "data": [],
            "meta": {
                "error": str(e),
                "query": query
            }
        }