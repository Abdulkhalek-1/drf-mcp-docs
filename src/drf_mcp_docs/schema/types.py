from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthMethod:
    name: str
    type: str  # bearer, basic, apiKey, oauth2
    description: str = ""
    header_name: str | None = None
    scheme: str | None = None


@dataclass(frozen=True)
class Parameter:
    name: str
    location: str  # path, query, header
    required: bool = False
    schema: dict = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class RequestBody:
    content_type: str = "application/json"
    schema: dict = field(default_factory=dict)
    required: bool = False
    example: dict | None = None


@dataclass(frozen=True)
class Response:
    status_code: str = "200"
    description: str = ""
    schema: dict | None = None
    example: dict | None = None


@dataclass(frozen=True)
class Endpoint:
    path: str
    method: str
    operation_id: str = ""
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    request_body: RequestBody | None = None
    responses: dict[str, Response] = field(default_factory=dict)
    auth_required: bool = False
    auth_methods: list[str] = field(default_factory=list)
    deprecated: bool = False


@dataclass(frozen=True)
class Tag:
    name: str
    description: str = ""


@dataclass(frozen=True)
class APIOverview:
    title: str = ""
    description: str = ""
    version: str = ""
    base_url: str = ""
    auth_methods: list[AuthMethod] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    endpoint_count: int = 0


@dataclass(frozen=True)
class SchemaDefinition:
    name: str
    type: str = "object"
    properties: dict = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    description: str = ""
