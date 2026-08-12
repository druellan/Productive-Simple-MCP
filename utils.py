from typing import Any, Dict
import json
from html import escape
import bleach
from config import config
from productive_client import ProductiveAPIError


def get_webapp_url(resource_type: str, resource_id: str) -> str:
    """Generate Productive web app URL for a resource.
    
    Args:
        resource_type: Type of resource ('projects', 'tasks', etc.)
        resource_id: The resource ID
        
    Returns:
        URL to view the resource in Productive web app
    """
    org_id = config.organization
    # Productive URLs follow pattern: https://app.productive.io/{org-id}/[resource-type]/{id}
    return f"https://app.productive.io/{org_id}/{resource_type}/{resource_id}"

def _filter_attributes(attributes: Dict[str, Any], obj_type: str) -> Dict[str, Any]:
    """Filter out unwanted attributes and strip HTML from specific fields based on object type.
    
    Args:
        attributes: The attributes dictionary to filter
        obj_type: The type of object (tasks, pages, page, etc.)
    """
    filtered = dict(attributes)
    
    # Fields to remove per type
    remove_fields = {
        'tasks': ['creation_method_id', 'email_key', 'placement'],
        'comments': [],
        'todos': [],
        'pages': ['preferences', 'cover_image_meta', 'custom_fields', 'version_number', 'position'],
        'page': ['preferences', 'cover_image_meta', 'custom_fields', 'version_number', 'position'],
        'attachments': ['attachable_type', 'attachable_id'],
        'projects': [
            'sample_data',
            'template',
            'time_on_tasks',
            'project_color_id',
            'duplication_status',
            'project_type_id',
            'preferences',
            'number'  # Redundant with project_number
        ],
    }
    
    # Fields to strip HTML from per type
    html_fields = {
        'tasks': ['description'],
        'comments': ['body'],
        'todos': ['description'],
        'pages': [],
        'page': [],
    }
    
    # Remove unwanted fields
    for field in remove_fields.get(obj_type, []):
        filtered.pop(field, None)
    
    # Strip HTML from specified fields
    for field in html_fields.get(obj_type, []):
        if field in filtered and isinstance(filtered[field], str):
            filtered[field] = bleach.clean(filtered[field], tags=[], strip=True)
    
    return filtered


def _filter_task_list_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Filter task attributes for list views - keep only essential fields for browsing.
    
    When listing multiple tasks, we want just enough info to identify and select tasks,
    without overwhelming the LLM with descriptions and metadata.
    """
    # Keep only these essential fields
    essential_fields = [
        'title',
        'task_number',
        'closed',
        'created_at',
        'updated_at',
        'initial_estimate',
        'remaining_time',
        'worked_time',
        'billable_time',
        'closed_at',
        'type_id',
        'private',
        'workflow_status_name'  # Add custom status name
    ]
    
    filtered = {k: v for k, v in attributes.items() if k in essential_fields}
    return filtered

def remove_null_and_empty(obj: Any) -> Any:
    """Recursively remove null, empty dicts/lists, and empty strings from a dict/list.

    Additionally:
    - Remove meta.included when it's False
    - Remove meta.settings when present
    - Remove pagination links
    - Remove empty meta dicts and empty parent objects after cleanup
    - Filter out unwanted task attributes
    - Remove organization relationships (redundant)
    """
    if isinstance(obj, dict):
        result = {}
        
        for key, value in obj.items():
            # Skip pagination links - not useful for LLMs
            if key == "links":
                continue
            
            # Skip organization relationships - redundant
            if key == "relationships" and isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != "organization"}
                
            cleaned_value = remove_null_and_empty(value)
            
            # Skip empty values
            if cleaned_value in (None, "", {}, []):
                continue
            
            # Filter out unwanted attributes based on object type
            if key == "attributes" and isinstance(cleaned_value, dict):
                obj_type = obj.get('type')
                cleaned_value = _filter_attributes(cleaned_value, obj_type)
            
            # Handle meta objects specially
            if key == "meta" and isinstance(cleaned_value, dict):
                cleaned_meta = _clean_meta_object(cleaned_value)
                if cleaned_meta:
                    result[key] = cleaned_meta
            else:
                result[key] = cleaned_value
        
        return result
    
    elif isinstance(obj, list):
        result = []
        for item in obj:
            cleaned_item = remove_null_and_empty(item)
            if cleaned_item not in (None, "", {}, []):
                result.append(cleaned_item)
        return result
    
    else:
        return obj


def _clean_meta_object(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Clean meta object by removing unwanted fields.
    
    Args:
        meta: The meta dictionary from API response
        
    Returns:
        Cleaned meta dictionary with unwanted fields removed
    """
    cleaned = dict(meta)
    
    # Remove 'included' when it's explicitly False
    if cleaned.get("included") is False:
        cleaned.pop("included", None)
    
    # Remove 'settings' if present
    cleaned.pop("settings", None)
    
    return cleaned


def filter_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Filter Productive API response: remove sensitive fields and clean empty values.
    
    Also adds webapp_url to resources for easy access to the Productive web interface.
    For tasks, also extracts and adds workflow_status_name from included data.
    """
    filtered = remove_null_and_empty(response)
    
    # Add webapp URLs and workflow status names to resources
    if isinstance(filtered, dict) and "data" in filtered:
        included = response.get("included", [])
        
        if isinstance(filtered["data"], dict):
            # Single resource
            item = filtered["data"]
            _add_webapp_url(item)
            
            # Add workflow status name for tasks
            if item.get("type") == "tasks":
                workflow_status_name = _extract_workflow_status_name(item, included)
                if workflow_status_name and "attributes" in item:
                    item["attributes"]["workflow_status_name"] = workflow_status_name
                    
        elif isinstance(filtered["data"], list):
            # Multiple resources
            for item in filtered["data"]:
                _add_webapp_url(item)
                
                # Add workflow status name for tasks
                if item.get("type") == "tasks":
                    workflow_status_name = _extract_workflow_status_name(item, included)
                    if workflow_status_name and "attributes" in item:
                        item["attributes"]["workflow_status_name"] = workflow_status_name
    
    return filtered


def _add_webapp_url(item: Dict[str, Any]) -> None:
    """Add webapp_url to a resource item in-place.
    
    Modifies the item dict to include a webapp_url field for easy access.
    """
    if not isinstance(item, dict):
        return
    
    resource_type = item.get("type")
    resource_id = item.get("id")
    
    if resource_type and resource_id:
        item["webapp_url"] = get_webapp_url(resource_type, resource_id)


def _extract_workflow_status_name(item: Dict[str, Any], included: list) -> str:
    """Extract workflow status name from included data.
    
    Args:
        item: Task item with relationships
        included: List of included resources from API response
        
    Returns:
        Workflow status name or None if not found
    """
    if not isinstance(item, dict) or not isinstance(included, list):
        return None
    
    # Get workflow_status relationship
    relationships = item.get("relationships", {})
    workflow_status_rel = relationships.get("workflow_status", {})
    workflow_status_data = workflow_status_rel.get("data")
    
    if not workflow_status_data or not isinstance(workflow_status_data, dict):
        return None
    
    workflow_status_id = workflow_status_data.get("id")
    if not workflow_status_id:
        return None
    
    # Find the workflow_status in included data
    for included_item in included:
        if (isinstance(included_item, dict) and 
            included_item.get("type") == "workflow_statuses" and 
            included_item.get("id") == workflow_status_id):
            
            attributes = included_item.get("attributes", {})
            return attributes.get("name")
    
    return None


def filter_task_list_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Filter task list responses to show only essential fields for browsing.
    
    Removes:
    - descriptions (can be very long)
    - relationships (not needed for list view)
    - non-essential metadata
    
    Keeps only what's needed to identify and select tasks.
    Also adds webapp_url and workflow_status_name for easy access.
    """
    if not isinstance(response, dict):
        return response
    
    filtered = {}
    included = response.get("included", [])
    
    # Process data array
    if "data" in response and isinstance(response["data"], list):
        filtered_data = []
        for item in response["data"]:
            if isinstance(item, dict) and item.get("type") == "tasks":
                filtered_item = {
                    "id": item.get("id"),
                    "type": item.get("type"),
                }
                
                # Filter attributes to essential fields only
                if "attributes" in item:
                    attrs = _filter_task_list_attributes(item["attributes"])
                    
                    # Extract and add workflow status name
                    workflow_status_name = _extract_workflow_status_name(item, included)
                    if workflow_status_name:
                        attrs["workflow_status_name"] = workflow_status_name
                    
                    filtered_item["attributes"] = attrs
                
                # Add webapp URL for easy access
                _add_webapp_url(filtered_item)

                filtered_data.append(filtered_item)
            else:
                filtered_data.append(item)
        
        filtered["data"] = filtered_data
    
    # Keep meta if present (has useful info like total_count)
    if "meta" in response:
        filtered["meta"] = _clean_meta_object(response["meta"])
    
    # Clean up empty values
    return remove_null_and_empty(filtered)


def filter_page_list_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Filter page list responses to keep metadata and drop heavy body field.

    - Removes attributes.body from each page item
    - Keeps other attributes as-is after general cleaning
    - Preserves meta (cleaned) and adds webapp_url per item
    """
    if not isinstance(response, dict):
        return response

    filtered: Dict[str, Any] = {}

    # Process data array
    if "data" in response and isinstance(response["data"], list):
        filtered_data = []
        for item in response["data"]:
            if isinstance(item, dict) and item.get("type") == "pages":
                new_item = {"id": item.get("id"), "type": item.get("type")}
                attrs = item.get("attributes", {})
                if isinstance(attrs, dict):
                    # Copy attributes without body
                    new_attrs = dict(attrs)
                    new_attrs.pop("body", None)
                    new_item["attributes"] = new_attrs
                _add_webapp_url(new_item)
                filtered_data.append(new_item)
            else:
                filtered_data.append(item)
        filtered["data"] = filtered_data

    # Keep meta if present (has useful info like total_count)
    if "meta" in response:
        filtered["meta"] = _clean_meta_object(response["meta"])

    return remove_null_and_empty(filtered)


# ---------------------------------------------------------------------------
# ProseMirror -> HTML conversion
#
# Productive stores page bodies in ProseMirror JSON. When an agent echoes the
# body it received from get_page back into update_page, we convert it to HTML
# internally so the page is written correctly instead of being corrupted.
# ---------------------------------------------------------------------------

_MARK_TAGS = {
    "strong": ("<strong>", "</strong>"),
    "em": ("<em>", "</em>"),
    "underline": ("<u>", "</u>"),
    "strike": ("<del>", "</del>"),
    "code": ("<code>", "</code>"),
}


def _pm_apply_marks(inner: str, marks: list) -> str:
    """Wrap text in its ProseMirror marks (innermost first -> outermost)."""
    if not marks:
        return inner
    out = inner
    for mark in reversed(marks):
        if not isinstance(mark, dict):
            continue
        mtype = mark.get("type")
        attrs = mark.get("attrs") or {}
        if mtype in _MARK_TAGS:
            open_tag, close_tag = _MARK_TAGS[mtype]
            out = open_tag + out + close_tag
        elif mtype == "link":
            href = attrs.get("href") or ""
            title = attrs.get("title")
            title_attr = f' title="{escape(title)}"' if title else ""
            out = f'<a href="{escape(href)}"{title_attr}>{out}</a>'
        elif mtype == "discussion":
            did = attrs.get("discussionId") or ""
            rid = attrs.get("resolvedId") or ""
            out = f'<span discussion-id="{escape(did)}" resolved-id="{escape(rid)}">{out}</span>'
        elif mtype == "styles":
            style = attrs.get("style") or ""
            if style:
                out = f'<span style="{escape(style)}">{out}</span>'
    return out


def _pm_align_style(attrs: Dict[str, Any]) -> str:
    align = attrs.get("horizontalAlign")
    if align:
        return f' style="text-align: {escape(align)}"'
    return ""


def _pm_mention(node: Dict[str, Any]) -> str:
    attrs = node.get("attrs") or {}
    mtype = attrs.get("type") or "user"
    mid = attrs.get("id") or ""
    label = attrs.get("label") or ""
    if not label:
        label = "".join(
            c.get("text", "")
            for c in (node.get("content") or [])
            if isinstance(c, dict) and c.get("type") == "text"
        )
    avatar = attrs.get("avatarUrl") or ""
    parts = [
        f'mention-type="{escape(mtype)}"',
        f'mention-id="{escape(mid)}"',
        f'mention-label="{escape(label)}"',
    ]
    if avatar:
        parts.append(f'mention-avatar-url="{escape(avatar)}"')
    return f'<span {" ".join(parts)}>{escape(label)}</span>'


def _pm_image(node: Dict[str, Any]) -> str:
    attrs = node.get("attrs") or {}
    src = attrs.get("src") or attrs.get("url") or ""
    alt = attrs.get("alt") or ""
    title = attrs.get("title") or ""
    width = attrs.get("width")
    parts = [f'src="{escape(src)}"', f'alt="{escape(alt)}"']
    if title:
        parts.append(f'title="{escape(title)}"')
    if width is not None:
        parts.append(f'width="{escape(str(width))}"')
    return f'<img {" ".join(parts)}>'


def _pm_var(node: Dict[str, Any]) -> str:
    attrs = node.get("attrs") or {}
    name = attrs.get("name") or attrs.get("var") or ""
    return f'<span var="{escape(name)}"></span>'


def _pm_file(node: Dict[str, Any]) -> str:
    attrs = node.get("attrs") or {}
    ftype = attrs.get("fileType") or attrs.get("type") or ""
    url = attrs.get("url") or ""
    name = attrs.get("name") or ""
    return (
        f'<span file-type="{escape(ftype)}" url="{escape(url)}" '
        f'name="{escape(name)}">{escape(name)}</span>'
    )


def _pm_render(node: Any) -> str:
    """Render a single ProseMirror node as Productive HTML."""
    if not isinstance(node, dict):
        return ""
    ntype = node.get("type")
    attrs = node.get("attrs") or {}
    content = node.get("content") or []

    if ntype == "text":
        return _pm_apply_marks(escape(node.get("text", "")), node.get("marks") or [])

    if ntype == "br":
        return "<br>"
    if ntype == "mention":
        return _pm_mention(node)
    if ntype == "image":
        return _pm_image(node)
    if ntype == "var":
        return _pm_var(node)
    if ntype == "file":
        return _pm_file(node)

    style = _pm_align_style(attrs)
    inner = "".join(_pm_render(c) for c in content)

    if ntype == "paragraph":
        return f"<p{style}>{inner}</p>"
    if ntype == "heading":
        level = max(1, min(int(attrs.get("level") or 1), 3))
        return f"<h{level}{style}>{inner}</h{level}>"
    if ntype == "ul":
        if attrs.get("type") == "checklist":
            return f'<ul type="checklist">{inner}</ul>'
        return f"<ul>{inner}</ul>"
    if ntype == "ol":
        start = attrs.get("start")
        start_attr = f' start="{int(start)}"' if start is not None else ""
        return f"<ol{start_attr}>{inner}</ol>"
    if ntype == "li":
        checked = attrs.get("checked")
        if checked is not None:
            checked = "true" if checked else "false"
            return f'<li type="checklist_item" checked="{checked}">{inner}</li>'
        return f"<li>{inner}</li>"
    if ntype == "checklist":
        return f'<ul type="checklist">{inner}</ul>'
    if ntype == "divider":
        return "<hr>"
    if ntype == "blockquote":
        return f"<blockquote>{inner}</blockquote>"
    if ntype in ("codeblock", "code_block"):
        lang = attrs.get("language") or attrs.get("codeblock-language") or ""
        lang_attr = f' codeblock-language="{escape(lang)}"' if lang else ""
        return f"<pre{lang_attr}><code>{inner}</code></pre>"
    if ntype == "table":
        return f"<table>{inner}</table>"
    if ntype in ("table_row", "tableRow"):
        return f"<tr>{inner}</tr>"
    if ntype in ("table_header_cell", "tableHeaderCell"):
        return f"<th>{inner}</th>"
    if ntype in ("table_cell", "tableCell"):
        return f"<td>{inner}</td>"
    if ntype == "banner":
        btype = attrs.get("type") or "info"
        return f'<banner type="{escape(btype)}">{inner}</banner>'
    if ntype == "columns":
        count = len(content) or int(attrs.get("count") or 0)
        count_attr = f' data-column-count="{count}"' if count else ""
        return f'<div data-columns{count_attr}>{inner}</div>'
    if ntype == "column":
        return f'<div data-column>{inner}</div>'

    # Unknown node: degrade to its rendered content so nothing is lost.
    return inner


def prosemirror_to_html(body: Any) -> str:
    """Convert a ProseMirror document (dict or JSON string) to Productive HTML."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (ValueError, TypeError):
            return ""
    if not isinstance(body, dict):
        return ""
    return _pm_render(body)


def _coerce_parsed_json(parsed: Any) -> str:
    """Resolve an already-parsed JSON payload into HTML page content."""
    if isinstance(parsed, dict):
        if parsed.get("type") == "doc":
            return _pm_render(parsed)

        data = parsed.get("data")
        if isinstance(data, dict):
            attrs = data.get("attributes") or {}
            body = attrs.get("body")
            if body is not None:
                if isinstance(body, dict) and body.get("type") == "doc":
                    return _pm_render(body)
                if isinstance(body, str):
                    try:
                        parsed_body = json.loads(body)
                    except (ValueError, TypeError):
                        parsed_body = None
                    if isinstance(parsed_body, dict) and parsed_body.get("type") == "doc":
                        return _pm_render(parsed_body)
            html = attrs.get("html") or data.get("html")
            if isinstance(html, str):
                return html

        html = parsed.get("html")
        if isinstance(html, str):
            return html

    raise ProductiveAPIError(
        "Unrecognized JSON content for page body; expected HTML markup or the "
        "ProseMirror document returned by get_page.",
        400,
        "INVALID_PAGE_CONTENT",
    )


def coerce_page_content_to_html(content: Any) -> str:
    """Normalize page content to HTML.

    HTML passes through unchanged. A JSON payload (the ProseMirror document
    returned by get_page, a JSON:API envelope, or an {"html": ...} wrapper) is
    converted to HTML internally. Raises ProductiveAPIError for JSON that
    cannot be interpreted.
    """
    if content is None:
        return ""
    if isinstance(content, dict):
        return _coerce_parsed_json(content)
    if not isinstance(content, str):
        content = str(content)

    stripped = content.strip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        return content

    try:
        parsed = json.loads(stripped)
    except (ValueError, TypeError):
        return content

    if not isinstance(parsed, (dict, list)):
        return content
    return _coerce_parsed_json(parsed)
