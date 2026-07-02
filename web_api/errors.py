"""Structured Web API errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ApiError(Exception):
    """Error that can be safely exposed through the Web API."""

    code: str
    message: str
    status_code: int = 400
    detail: str | None = None
    context: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the public API error shape."""

        error: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.detail:
            error["detail"] = self.detail
        if self.context:
            error["context"] = self.context
        return {"ok": False, "error": error}
