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
