from fastmcp import Context
from fastmcp.tools.tool import ToolResult

from config import config
from productive_client import client, ProductiveAPIError
from tools_read import _handle_productive_api_error
from utils import filter_response


async def _ensure_writes_enabled(ctx: Context, operation_name: str) -> None:
    """Block write operations globally when READ_ONLY mode is enabled."""
    if config.read_only:
        message = (
            f"READ_ONLY mode is enabled. '{operation_name}' is not allowed. "
            "Set READ_ONLY=false to enable write tools."
        )
        await ctx.error(message)
        raise ProductiveAPIError(message, 403, "READ_ONLY_ENABLED")


async def create_task(
    ctx: Context,
    title: str,
    project_id: int,
    description: str = None,
    board_id: int = None,
    task_list_id: int = None,
    assignee_id: int = None,
    due_date: str = None,
    status: str = "open",
) -> ToolResult:
    """Create a new task in Productive with optional relationships."""
    try:
        await _ensure_writes_enabled(ctx, "create_task")

        normalized_status = status.lower().strip()
        if normalized_status not in ("open", "closed"):
            raise ProductiveAPIError(
                "status must be one of: 'open', 'closed'",
                400,
                "INVALID_PARAMS",
            )

        await ctx.info(f"Creating task '{title}' in project {project_id}")

        task_payload = {
            "data": {
                "type": "tasks",
                "attributes": {
                    "title": title,
                    "status": 1 if normalized_status == "open" else 2,
                },
                "relationships": {
                    "project": {
                        "data": {
                            "id": str(project_id),
                            "type": "projects",
                        }
                    }
                },
            }
        }

        if description is not None:
            task_payload["data"]["attributes"]["description"] = description
        if due_date is not None:
            task_payload["data"]["attributes"]["due_date"] = due_date
        if board_id is not None:
            task_payload["data"]["relationships"]["board"] = {
                "data": {
                    "id": str(board_id),
                    "type": "boards",
                }
            }
        if task_list_id is not None:
            task_payload["data"]["relationships"]["task_list"] = {
                "data": {
                    "id": str(task_list_id),
                    "type": "task_lists",
                }
            }
        if assignee_id is not None:
            task_payload["data"]["relationships"]["assignee"] = {
                "data": {
                    "id": str(assignee_id),
                    "type": "people",
                }
            }

        result = await client.create_task(data=task_payload)
        await ctx.info("Successfully created task")

        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "task creation")
    except Exception as e:
        await ctx.error(f"Unexpected error creating task: {str(e)}")
        raise e


async def update_task(
    ctx: Context,
    task_id: int,
    title: str = None,
    description: str = None,
    assignee_id: int = None,
    due_date: str = None,
    status: str = None,
    board_id: int = None,
    task_list_id: int = None,
) -> ToolResult:
    """Update an existing task in Productive. Only provided fields are modified (PATCH)."""
    try:
        await _ensure_writes_enabled(ctx, "update_task")

        if not any([
            title is not None,
            description is not None,
            assignee_id is not None,
            due_date is not None,
            status is not None,
            board_id is not None,
            task_list_id is not None,
        ]):
            raise ProductiveAPIError(
                "At least one field must be provided for update",
                400,
                "INVALID_PARAMS",
            )

        await ctx.info(f"Updating task {task_id}")

        task_payload: dict = {
            "data": {
                "type": "tasks",
                "id": str(task_id),
                "attributes": {},
                "relationships": {},
            }
        }

        # Attributes (only include if provided)
        if title is not None:
            task_payload["data"]["attributes"]["title"] = title
        if description is not None:
            task_payload["data"]["attributes"]["description"] = description
        if due_date is not None:
            task_payload["data"]["attributes"]["due_date"] = due_date
        if status is not None:
            normalized_status = status.lower().strip()
            if normalized_status not in ("open", "closed"):
                raise ProductiveAPIError(
                    "status must be one of: 'open', 'closed'",
                    400,
                    "INVALID_PARAMS",
                )
            task_payload["data"]["attributes"]["status"] = (
                1 if normalized_status == "open" else 2
            )

        # Relationships (only include if provided)
        if assignee_id is not None:
            # Use 0 or negative to unassign
            if assignee_id <= 0:
                task_payload["data"]["relationships"]["assignee"] = {
                    "data": None
                }
            else:
                task_payload["data"]["relationships"]["assignee"] = {
                    "data": {"id": str(assignee_id), "type": "people"}
                }
        if board_id is not None:
            task_payload["data"]["relationships"]["board"] = {
                "data": {"id": str(board_id), "type": "boards"}
            }
        if task_list_id is not None:
            task_payload["data"]["relationships"]["task_list"] = {
                "data": {"id": str(task_list_id), "type": "task_lists"}
            }

        # Clean empty sections to keep payload lean
        if not task_payload["data"]["attributes"]:
            del task_payload["data"]["attributes"]
        if not task_payload["data"]["relationships"]:
            del task_payload["data"]["relationships"]

        result = await client.update_task(task_id, data=task_payload)
        await ctx.info("Successfully updated task")
        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "task update")
    except Exception as e:
        await ctx.error(f"Unexpected error updating task: {str(e)}")
        raise e


async def delete_task(
    ctx: Context,
    task_id: int,
) -> ToolResult:
    """Delete a task from Productive by ID. This action is irreversible."""
    try:
        await _ensure_writes_enabled(ctx, "delete_task")

        await ctx.info(f"Deleting task {task_id}")
        await client.delete_task(task_id)
        await ctx.info("Successfully deleted task")

        return ToolResult(
            f"Task {task_id} has been successfully deleted."
        )

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "task deletion")
    except Exception as e:
        await ctx.error(f"Unexpected error deleting task: {str(e)}")
        raise e


async def create_comment(
    ctx: Context,
    body: str,
    task_id: int = None,
    project_id: int = None,
) -> ToolResult:
    """Create a new comment in Productive. A comment must be attached to either a task or a project."""
    try:
        await _ensure_writes_enabled(ctx, "create_comment")

        if not task_id and not project_id:
            raise ProductiveAPIError(
                "At least one of task_id or project_id is required",
                400,
                "INVALID_PARAMS",
            )

        target = f"task {task_id}" if task_id else f"project {project_id}"
        await ctx.info(f"Creating comment on {target}")

        comment_payload: dict = {
            "data": {
                "type": "comments",
                "attributes": {
                    "body": body,
                },
                "relationships": {},
            }
        }

        if task_id is not None:
            comment_payload["data"]["relationships"]["task"] = {
                "data": {"id": str(task_id), "type": "tasks"}
            }
        if project_id is not None:
            comment_payload["data"]["relationships"]["project"] = {
                "data": {"id": str(project_id), "type": "projects"}
            }

        result = await client.create_comment(data=comment_payload)
        await ctx.info("Successfully created comment")
        filtered = filter_response(result)
        return filtered
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "comment creation")
    except Exception as e:
        await ctx.error(f"Unexpected error creating comment: {str(e)}")
        raise e


async def update_comment(
    ctx: Context,
    comment_id: int,
    body: str,
) -> ToolResult:
    """Update an existing comment in Productive. Only the body can be modified."""
    try:
        await _ensure_writes_enabled(ctx, "update_comment")

        await ctx.info(f"Updating comment {comment_id}")

        comment_payload: dict = {
            "data": {
                "type": "comments",
                "id": str(comment_id),
                "attributes": {
                    "body": body,
                },
            }
        }

        result = await client.update_comment(comment_id, data=comment_payload)
        await ctx.info("Successfully updated comment")
        filtered = filter_response(result)
        return filtered
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "comment update")
    except Exception as e:
        await ctx.error(f"Unexpected error updating comment: {str(e)}")
        raise e


async def delete_comment(
    ctx: Context,
    comment_id: int,
) -> ToolResult:
    """Delete a comment from Productive by ID. This action is irreversible."""
    try:
        await _ensure_writes_enabled(ctx, "delete_comment")

        await ctx.info(f"Deleting comment {comment_id}")
        await client.delete_comment(comment_id)
        await ctx.info("Successfully deleted comment")
        return ToolResult(f"Comment {comment_id} has been successfully deleted.")
    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "comment deletion")
    except Exception as e:
        await ctx.error(f"Unexpected error deleting comment: {str(e)}")
        raise e


async def create_time_entry(
    ctx: Context,
    date: str,
    time: float,
    person_id: int,
    task_id: int = None,
    service_id: int = None,
    note: str = None,
) -> ToolResult:
    """Create a new time entry in Productive for time tracking."""
    try:
        await _ensure_writes_enabled(ctx, "create_time_entry")

        if task_id is None and service_id is None:
            raise ProductiveAPIError(
                "Either task_id or service_id must be provided",
                400,
                "INVALID_PARAMS",
            )

        await ctx.info(f"Creating time entry for {time} hours on {date}")

        time_entry_payload = {
            "data": {
                "type": "time_entries",
                "attributes": {
                    "date": date,
                    "time": time,
                },
                "relationships": {
                    "person": {
                        "data": {
                            "id": str(person_id),
                            "type": "people",
                        }
                    }
                },
            }
        }

        if task_id is not None:
            time_entry_payload["data"]["relationships"]["task"] = {
                "data": {
                    "id": str(task_id),
                    "type": "tasks",
                }
            }
        if service_id is not None:
            time_entry_payload["data"]["relationships"]["service"] = {
                "data": {
                    "id": str(service_id),
                    "type": "services",
                }
            }
        if note is not None:
            time_entry_payload["data"]["attributes"]["note"] = note

        result = await client.create_time_entry(data=time_entry_payload)
        await ctx.info("Successfully created time entry")

        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "time entry creation")
    except Exception as e:
        await ctx.error(f"Unexpected error creating time entry: {str(e)}")
        raise e


async def update_time_entry(
    ctx: Context,
    time_entry_id: int,
    date: str = None,
    time: float = None,
    person_id: int = None,
    task_id: int = None,
    service_id: int = None,
    note: str = None,
) -> ToolResult:
    """Update an existing time entry in Productive. Only provided fields are modified (PATCH)."""
    try:
        await _ensure_writes_enabled(ctx, "update_time_entry")

        if not any([
            date is not None,
            time is not None,
            person_id is not None,
            task_id is not None,
            service_id is not None,
            note is not None,
        ]):
            raise ProductiveAPIError(
                "At least one field must be provided for update",
                400,
                "INVALID_PARAMS",
            )

        await ctx.info(f"Updating time entry {time_entry_id}")

        time_entry_payload: dict = {
            "data": {
                "type": "time_entries",
                "id": str(time_entry_id),
                "attributes": {},
                "relationships": {},
            }
        }

        # Attributes (only include if provided)
        if date is not None:
            time_entry_payload["data"]["attributes"]["date"] = date
        if time is not None:
            time_entry_payload["data"]["attributes"]["time"] = time
        if note is not None:
            time_entry_payload["data"]["attributes"]["note"] = note

        # Relationships (only include if provided)
        if person_id is not None:
            time_entry_payload["data"]["relationships"]["person"] = {
                "data": {"id": str(person_id), "type": "people"}
            }
        if task_id is not None:
            time_entry_payload["data"]["relationships"]["task"] = {
                "data": {"id": str(task_id), "type": "tasks"}
            }
        if service_id is not None:
            time_entry_payload["data"]["relationships"]["service"] = {
                "data": {"id": str(service_id), "type": "services"}
            }

        # Clean empty sections to keep payload lean
        if not time_entry_payload["data"]["attributes"]:
            del time_entry_payload["data"]["attributes"]
        if not time_entry_payload["data"]["relationships"]:
            del time_entry_payload["data"]["relationships"]

        result = await client.update_time_entry(time_entry_id, data=time_entry_payload)
        await ctx.info("Successfully updated time entry")
        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "time entry update")
    except Exception as e:
        await ctx.error(f"Unexpected error updating time entry: {str(e)}")
        raise e


async def delete_time_entry(
    ctx: Context,
    time_entry_id: int,
) -> ToolResult:
    """Delete a time entry from Productive by ID. This action is irreversible."""
    try:
        await _ensure_writes_enabled(ctx, "delete_time_entry")

        await ctx.info(f"Deleting time entry {time_entry_id}")
        await client.delete_time_entry(time_entry_id)
        await ctx.info("Successfully deleted time entry")

        return ToolResult(
            f"Time entry {time_entry_id} has been successfully deleted."
        )

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "time entry deletion")
    except Exception as e:
        await ctx.error(f"Unexpected error deleting time entry: {str(e)}")
        raise e


async def create_page(
    ctx: Context,
    title: str,
    project_id: int,
    content: str = None,
) -> ToolResult:
    """Create a new page/document in Productive."""
    try:
        await _ensure_writes_enabled(ctx, "create_page")

        await ctx.info(f"Creating page '{title}' in project {project_id}")

        page_payload = {
            "data": {
                "type": "pages",
                "attributes": {
                    "title": title,
                },
                "relationships": {
                    "project": {
                        "data": {
                            "id": str(project_id),
                            "type": "projects",
                        }
                    }
                },
            }
        }

        if content is not None:
            page_payload["data"]["attributes"]["content"] = content

        result = await client.create_page(data=page_payload)
        await ctx.info("Successfully created page")

        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "page creation")
    except Exception as e:
        await ctx.error(f"Unexpected error creating page: {str(e)}")
        raise e


async def update_page(
    ctx: Context,
    page_id: int,
    title: str = None,
    content: str = None,
) -> ToolResult:
    """Update an existing page/document in Productive. Only provided fields are modified (PATCH)."""
    try:
        await _ensure_writes_enabled(ctx, "update_page")

        if not any([
            title is not None,
            content is not None,
        ]):
            raise ProductiveAPIError(
                "At least one field must be provided for update",
                400,
                "INVALID_PARAMS",
            )

        await ctx.info(f"Updating page {page_id}")

        page_payload: dict = {
            "data": {
                "type": "pages",
                "id": str(page_id),
                "attributes": {},
            }
        }

        # Attributes (only include if provided)
        if title is not None:
            page_payload["data"]["attributes"]["title"] = title
        if content is not None:
            page_payload["data"]["attributes"]["content"] = content

        result = await client.update_page(page_id, data=page_payload)
        await ctx.info("Successfully updated page")
        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "page update")
    except Exception as e:
        await ctx.error(f"Unexpected error updating page: {str(e)}")
        raise e


async def delete_page(
    ctx: Context,
    page_id: int,
) -> ToolResult:
    """Delete a page/document from Productive by ID. This action is irreversible."""
    try:
        await _ensure_writes_enabled(ctx, "delete_page")

        await ctx.info(f"Deleting page {page_id}")
        await client.delete_page(page_id)
        await ctx.info("Successfully deleted page")

        return ToolResult(
            f"Page {page_id} has been successfully deleted."
        )

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "page deletion")
    except Exception as e:
        await ctx.error(f"Unexpected error deleting page: {str(e)}")
        raise e


async def create_todo(
    ctx: Context,
    content: str,
    task_id: int,
) -> ToolResult:
    """Create a new todo checklist item in Productive."""
    try:
        await _ensure_writes_enabled(ctx, "create_todo")

        await ctx.info(f"Creating todo '{content}' for task {task_id}")

        todo_payload = {
            "data": {
                "type": "todos",
                "attributes": {
                    "content": content,
                },
                "relationships": {
                    "task": {
                        "data": {
                            "id": str(task_id),
                            "type": "tasks",
                        }
                    }
                },
            }
        }

        result = await client.create_todo(data=todo_payload)
        await ctx.info("Successfully created todo")

        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "todo creation")
    except Exception as e:
        await ctx.error(f"Unexpected error creating todo: {str(e)}")
        raise e


async def update_todo(
    ctx: Context,
    todo_id: int,
    content: str = None,
    completed: bool = None,
) -> ToolResult:
    """Update an existing todo checklist item in Productive. Only provided fields are modified (PATCH)."""
    try:
        await _ensure_writes_enabled(ctx, "update_todo")

        if not any([
            content is not None,
            completed is not None,
        ]):
            raise ProductiveAPIError(
                "At least one field must be provided for update",
                400,
                "INVALID_PARAMS",
            )

        await ctx.info(f"Updating todo {todo_id}")

        todo_payload: dict = {
            "data": {
                "type": "todos",
                "id": str(todo_id),
                "attributes": {},
            }
        }

        # Attributes (only include if provided)
        if content is not None:
            todo_payload["data"]["attributes"]["content"] = content
        if completed is not None:
            todo_payload["data"]["attributes"]["completed"] = completed

        result = await client.update_todo(todo_id, data=todo_payload)
        await ctx.info("Successfully updated todo")
        filtered = filter_response(result)
        return filtered

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "todo update")
    except Exception as e:
        await ctx.error(f"Unexpected error updating todo: {str(e)}")
        raise e


async def delete_todo(
    ctx: Context,
    todo_id: int,
) -> ToolResult:
    """Delete a todo checklist item from Productive by ID. This action is irreversible."""
    try:
        await _ensure_writes_enabled(ctx, "delete_todo")

        await ctx.info(f"Deleting todo {todo_id}")
        await client.delete_todo(todo_id)
        await ctx.info("Successfully deleted todo")

        return ToolResult(
            f"Todo {todo_id} has been successfully deleted."
        )

    except ProductiveAPIError as e:
        await _handle_productive_api_error(ctx, e, "todo deletion")
    except Exception as e:
        await ctx.error(f"Unexpected error deleting todo: {str(e)}")
        raise e
