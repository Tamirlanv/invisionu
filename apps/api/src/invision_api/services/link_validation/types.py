from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AvailabilityStatus = Literal["reachable", "unreachable", "timeout", "forbidden", "private_access", "invalid", "unknown"]
ProviderType = Literal["generic", "google_drive", "google_docs", "dropbox", "onedrive", "youtube", "vimeo", "unknown"]
ResourceType = Literal["web_page", "file", "video", "cloud_resource", "unknown"]


class LinkValidationRequest(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    application_id: UUID | None = None


class HttpProbeResult(BaseModel):
    final_url: str | None
    status_code: int | None
    content_type: str | None
    content_length: int | None
    redirected: bool
    redirect_count: int
    response_time_ms: int | None
    timeout: bool = False
    network_error: bool = False
    error_text: str | None = None


class NormalizedUrl(BaseModel):
    original_url: str
    normalized_url: str | None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParsedUrlContext(BaseModel):
    scheme: str
    hostname: str
    path: str
    query: str
    normalized_url: str


class ClassificationResult(BaseModel):
    provider: ProviderType
    resource_type: ResourceType
    warnings: list[str] = Field(default_factory=list)
    hints: dict[str, str] = Field(default_factory=dict)


class AvailabilityResult(BaseModel):
    is_reachable: bool
    status: AvailabilityStatus
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LinkValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    originalUrl: str
    normalizedUrl: str | None
    isValidFormat: bool
    isReachable: bool
    availabilityStatus: AvailabilityStatus
    provider: ProviderType
    resourceType: ResourceType
    statusCode: int | None
    contentType: str | None
    contentLength: int | None
    redirected: bool
    redirectCount: int
    responseTimeMs: int | None
    warnings: list[str]
    errors: list[str]
    confidence: float
