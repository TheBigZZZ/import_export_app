from __future__ import annotations

from collections.abc import Iterable

import httpx


def _normalize_text(text: object) -> str:
    return " ".join(str(text).split()).strip()


def _extract_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return _normalize_text(value)
            if isinstance(value, list):
                parts: list[str] = []
                for item in value:
                    if isinstance(item, dict):
                        location = item.get("loc") or []
                        field = None
                        if isinstance(location, Iterable):
                            location_list = list(location)
                            if location_list:
                                field = str(location_list[-1])
                        message = _normalize_text(item.get("msg") or item.get("message") or "Invalid value")
                        if field:
                            parts.append(f"{field}: {message}")
                        else:
                            parts.append(message)
                    else:
                        parts.append(_normalize_text(item))
                if parts:
                    return "; ".join(parts)

    if isinstance(payload, list):
        parts = []
        for item in payload:
            if isinstance(item, dict):
                message = item.get("msg") or item.get("message") or item.get("detail")
                if message:
                    parts.append(_normalize_text(message))
            elif item:
                parts.append(_normalize_text(item))
        if parts:
            return "; ".join(parts)

    return _normalize_text(response.text)


def friendly_http_error(response: httpx.Response, context: str) -> str:
    detail = _extract_detail(response)
    code = response.status_code

    if code == 401:
        return "Username or password is incorrect."
    if code == 403:
        return f"You do not have permission to {context.lower()}."
    if code == 404:
        return f"{context} was not found on the backend."
    if code == 409:
        return detail or f"{context} already exists."
    if code == 422:
        return detail or "Please check the highlighted fields and try again."
    if code == 423:
        return detail or "This account is temporarily locked. Please try again later."
    if code == 429:
        return "Too many attempts. Please wait and try again."
    if code >= 500:
        return f"{context} failed because the server had a problem. Please try again."

    if detail:
        return detail
    return f"{context} failed with status {code}."


def friendly_exception_message(exc: Exception, context: str) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f"{context} timed out. The backend took too long to respond."
    if isinstance(exc, httpx.RequestError):
        return f"Could not reach the backend for {context.lower()}. Check the backend URL and network connection."

    message = _normalize_text(exc)
    if message:
        return message
    return f"{context} could not be completed."