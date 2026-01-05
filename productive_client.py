import httpx
import asyncio
from typing import Dict, Any, Optional
from config import config

class ProductiveAPIError(Exception):
    """Custom exception for Productive API errors"""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)

class ProductiveClient:
    """Async HTTP client for Productive API"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers=config.headers
        )
        self.max_retries = 3
        self.retry_delay = 1.0

    def _parse_error_response(self, response: httpx.Response, default_message: str = "Unknown error") -> tuple[str, str]:
        """Parse error response and return (message, error_code)"""
        try:
            error_data = response.json()
            message = error_data.get("message", default_message)
            error_code = error_data.get("errorCode", "UNKNOWN")
            return message, error_code
        except Exception:
            return f"HTTP {response.status_code}: {response.text}", "UNKNOWN"

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        """Determine if request should be retried based on status code and attempt count"""
        return attempt < self.max_retries and (status_code == 429 or status_code >= 500)

    async def _request(self, method: str, endpoint: str, params: Optional[dict] = None) -> Dict[str, Any]:
        """Make HTTP request to Productive API with retry logic for transient failures"""
        url = f"{config.base_url}{endpoint}"
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, params=params)
                
                # Success
                if response.status_code == 200:
                    return response.json()
                
                # Non-retryable errors
                if response.status_code == 401:
                    raise ProductiveAPIError("Unauthorized: Invalid API token", 401, "UNAUTHORIZED")
                
                if response.status_code == 404:
                    raise ProductiveAPIError("Resource not found", 404, "NOT_FOUND")
                
                # Retryable errors (429, 5xx)
                if self._should_retry(response.status_code, attempt):
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                
                # Final attempt or non-retryable 4xx error
                message, error_code = self._parse_error_response(
                    response,
                    "Rate limit exceeded" if response.status_code == 429 else "Server error"
                )
                raise ProductiveAPIError(message, response.status_code, error_code)
                        
            except httpx.RequestError as e:
                # Retry on network/connection errors
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise ProductiveAPIError(f"Request failed: {str(e)}")

    async def get_projects(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all projects"""
        return await self._request("GET", "/projects", params=params)

    async def get_tasks(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all tasks with workflow_status always included
        """
        if params is None:
            params = {}
        params["include"] = "workflow_status"
        return await self._request("GET", "/tasks", params=params)

    async def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get task by ID with workflow_status always included"""
        return await self._request("GET", f"/tasks/{str(task_id)}", params={"include": "workflow_status"})

    async def get_comments(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all comments
        """
        return await self._request("GET", "/comments", params=params)

    async def get_comment(self, comment_id: int) -> Dict[str, Any]:
        """Get comment by ID"""
        return await self._request("GET", f"/comments/{str(comment_id)}")

    async def get_todos(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all todos
        """
        return await self._request("GET", "/todos", params=params)

    async def get_todo(self, todo_id: int) -> Dict[str, Any]:
        """Get todo by ID"""
        return await self._request("GET", f"/todos/{str(todo_id)}")

    async def get_activities(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get activities with optional filtering"""
        return await self._request("GET", "/activities", params=params)

    async def get_pages(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all pages with optional filtering
        Supports filtering by project_id, creator_id, edited_at, id
        """
        return await self._request("GET", "/pages", params=params)

    async def get_page(self, page_id: int) -> Dict[str, Any]:
        """Get page by ID"""
        return await self._request("GET", f"/pages/{str(page_id)}")

    async def create_page(self, data: dict) -> Dict[str, Any]:
        """Create a new page
        
        Args:
            data: Page data payload following Productive API structure
        
        Returns:
            Created page data from API
        """
        return await self._request("POST", "/pages", params=data)

    async def update_page(self, page_id: int, data: dict) -> Dict[str, Any]:
        """Update an existing page
        
        Args:
            page_id: ID of the page to update
            data: Page data payload following Productive API structure
        
        Returns:
            Updated page data from API
        """
        return await self._request("PATCH", f"/pages/{str(page_id)}", params=data)

    async def get_attachments(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all attachments with optional filtering"""
        return await self._request("GET", "/attachments", params=params)

    async def get_attachment(self, attachment_id: int) -> Dict[str, Any]:
        """Get attachment by ID"""
        return await self._request("GET", f"/attachments/{str(attachment_id)}")

    async def get_people(self, params: Optional[dict] = None) -> Dict[str, Any]:
        """Get all people/team members"""
        return await self._request("GET", "/people", params=params)

    async def get_person(self, person_id: int) -> Dict[str, Any]:
        """Get person by ID"""
        return await self._request("GET", f"/people/{str(person_id)}")

    async def quick_search(self, query: str, search_types: Optional[list] = None, deep_search: bool = True, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Quick search across projects, tasks, pages, and actions"""
        if search_types is None:
            search_types = ["action", "project", "task", "page"]

        params = {
            "filter[query]": query,
            "filter[type]": ",".join(search_types),
            "filter[status]": "all",
            "filter[deep_search]": str(deep_search).lower(),
            "page": page,
            "per_page": per_page
        }

        return await self._request("GET", "/search/quick", params=params)

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global client instance
client = ProductiveClient()