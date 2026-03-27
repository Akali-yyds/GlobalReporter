"""
Common schema definitions.
"""
from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel):
    """Base response schema."""
    success: bool = True
    message: str = "OK"


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response schema."""
    total: int
    page: int
    page_size: int
    items: List[T]
