"""
MCP Input Validation and Sanitization

Defense-in-depth security controls for MCP operations:
- Input validation and sanitization
- URL/endpoint validation
- Request size validation
"""
import re
import ipaddress
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

ALLOWED_URL_SCHEMES = {"https", "http"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
MAX_URL_LENGTH = 2048
MAX_PAYLOAD_SIZE = 1024 * 1024
MAX_PLUGIN_NAME_LENGTH = 128


def validate_endpoint_url(url: str, allowed_hosts: Optional[List[str]] = None) -> List[str]:
    errors = []

    if not url or len(url) > MAX_URL_LENGTH:
        errors.append(f"URL must be 1-{MAX_URL_LENGTH} characters")
        return errors

    try:
        parsed = urlparse(url)
    except Exception:
        errors.append("Invalid URL format")
        return errors

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        errors.append(f"URL scheme must be one of: {', '.join(ALLOWED_URL_SCHEMES)}")

    if not parsed.netloc:
        errors.append("URL must have a valid host")

    host = parsed.hostname or ""
    if host.lower() in BLOCKED_HOSTS:
        errors.append(f"URL host '{host}' is not allowed")

    if allowed_hosts:
        if host not in allowed_hosts:
            errors.append(f"URL host '{host}' not in allowed hosts list")

    try:
        ipaddress.ip_address(host)
        errors.append("IP addresses are not allowed directly, use hostname")
    except ValueError:
        pass

    if re.search(r"[<>\"']", url):
        errors.append("URL contains potentially malicious characters")

    return errors


def validate_plugin_definition(plugin_def: Dict[str, Any]) -> List[str]:
    errors = []

    if not isinstance(plugin_def, dict):
        return ["Plugin definition must be an object"]

    name = plugin_def.get("name", "")
    if not name or len(name) > MAX_PLUGIN_NAME_LENGTH:
        errors.append(f"Plugin name must be 1-{MAX_PLUGIN_NAME_LENGTH} characters")

    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        errors.append("Plugin name contains invalid characters")

    endpoint_url = plugin_def.get("endpoint_url", "")
    errors.extend(validate_endpoint_url(endpoint_url))

    description = plugin_def.get("description", "")
    if len(description) > 1000:
        errors.append("Description must be 1000 characters or less")

    parameters = plugin_def.get("parameters", [])
    if not isinstance(parameters, list):
        errors.append("Parameters must be an array")
    elif len(parameters) > 50:
        errors.append("Maximum 50 parameters allowed")

    for i, param in enumerate(parameters):
        if not isinstance(param, dict):
            errors.append(f"Parameter {i} must be an object")
            continue
        if not param.get("name"):
            errors.append(f"Parameter {i} missing required 'name' field")
        param_type = param.get("type", "")
        if param_type not in {"string", "number", "integer", "boolean", "array", "object"}:
            errors.append(f"Parameter {i} has invalid type '{param_type}'")

    return errors


def sanitize_request_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = re.sub(r"[<>'\"&]", "", value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_request_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_request_payload(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def validate_request_size(payload: Dict[str, Any]) -> bool:
    import json
    size = len(json.dumps(payload))
    return size <= MAX_PAYLOAD_SIZE