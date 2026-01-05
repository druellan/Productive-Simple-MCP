from fastmcp import Context
from fastmcp.tools.tool import ToolResult

from productive_client import client, ProductiveAPIError
from utils import _handle_productive_api_error


async def create_page(
	ctx: Context,
	title: str,
	project_id: int,
	body: str = "",
	parent_page_id: int = None
) -> ToolResult:
	"""Create a new page in a project.

	- Wraps client.create_page() with proper JSON:API structure.
	- Body is stored as JSON string in attributes.body.
	- Raises ProductiveAPIError on API failure; errors are logged via ctx.
	"""
	try:
		await ctx.info(f"Creating page '{title}' in project {project_id}")
		
		# Build JSON:API compliant payload
		payload = {
			"data": {
				"type": "pages",
				"attributes": {
					"title": title,
					"body": body
				},
				"relationships": {
					"project": {
						"data": {
							"type": "projects",
							"id": str(project_id)
						}
					}
				}
			}
		}
		
		# Add parent page relationship if provided
		if parent_page_id is not None:
			payload["data"]["relationships"]["parent_page"] = {
				"data": {
					"type": "pages",
					"id": str(parent_page_id)
				}
			}
		
		result = await client.create_page(payload)
		await ctx.info("Successfully created page")
		
		return result
		
	except ProductiveAPIError as e:
		await _handle_productive_api_error(ctx, e, "page")
	except Exception as e:
		await ctx.error(f"Unexpected error creating page: {str(e)}")
		raise e


async def update_page(
	ctx: Context,
	page_id: int,
	title: str = None,
	body: str = None
) -> ToolResult:
	"""Update an existing page.

	- Wraps client.update_page() with proper JSON:API structure.
	- Only provided fields are updated (partial update).
	- Raises ProductiveAPIError on API failure; errors are logged via ctx.
	"""
	try:
		await ctx.info(f"Updating page {page_id}")
		
		# Build JSON:API compliant payload with only provided fields
		attributes = {}
		if title is not None:
			attributes["title"] = title
		if body is not None:
			attributes["body"] = body
		
		if not attributes:
			await ctx.warning("No fields provided for update")
			return {"message": "No changes made - no fields provided"}
		
		payload = {
			"data": {
				"type": "pages",
				"id": str(page_id),
				"attributes": attributes
			}
		}
		
		result = await client.update_page(page_id, payload)
		await ctx.info("Successfully updated page")
		
		return result
		
	except ProductiveAPIError as e:
		await _handle_productive_api_error(ctx, e, f"page {page_id}")
	except Exception as e:
		await ctx.error(f"Unexpected error updating page: {str(e)}")
		raise e
