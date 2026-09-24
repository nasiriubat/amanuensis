from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_serializer


class ApiModel(BaseModel):
    """SQLite drops timezone info; everything we store is UTC, so say so on the way out."""

    @field_serializer("*", mode="wrap", check_fields=False)
    def _utc_datetimes(self, value, nxt):
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return nxt(value)


# Lenient on purpose: self-hosted installs use intranet domains like user@lab.local
# that strict validators reject. We only need "something@something.something".
EmailStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]

# ------------------------------------------------------------------ auth / users


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ApiModel):
    id: str
    email: str
    display_name: str
    role: str
    must_change_password: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["admin", "user"] = "user"
    send_email: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)
    send_email: bool = False


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    new_password: str = Field(min_length=8, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


class UpdateMeIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


# ------------------------------------------------------------------ providers / models


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    adapter: Literal["openai_compat", "anthropic"]
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)  # empty string clears
    enabled: bool | None = None


class ModelOut(BaseModel):
    id: str
    name: str | None = None
    context_window: int | None = None


class ProviderOut(ApiModel):
    id: str
    name: str
    adapter: str
    base_url: str | None
    has_key: bool
    key_hint: str | None
    enabled: bool
    models: list[ModelOut]
    models_fetched_at: datetime | None
    models_error: str | None
    created_at: datetime


class PurposeOut(BaseModel):
    purpose: str
    description: str
    provider_id: str | None
    provider_name: str | None
    model: str | None


class PurposeAssign(BaseModel):
    provider_id: str | None
    model: str | None = Field(default=None, max_length=200)


class LlmTestIn(BaseModel):
    purpose: str
    prompt: str = "Reply with one short sentence confirming you can hear me."


class LlmTestOut(BaseModel):
    ok: bool
    provider: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


# ------------------------------------------------------------------ profiles


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    shareable: bool = False


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    shareable: bool | None = None


class ProfileOut(ApiModel):
    id: str
    slug: str
    name: str
    description: str | None
    owner_id: str
    owner_name: str
    shareable: bool
    status: str
    source_count: int
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ projects


ENTRY_PATTERN = "^(built|idea|draft)$"


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="other", max_length=64)
    entry: str = Field(default="built", pattern=ENTRY_PATTERN, description="Where the author starts")
    profile_id: str | None = None
    venue: str | None = Field(default=None, max_length=200)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    kind: str | None = Field(default=None, max_length=64)
    entry: str | None = Field(default=None, pattern=ENTRY_PATTERN)
    profile_id: str | None = None
    clear_profile: bool = False
    venue: str | None = Field(default=None, max_length=200)
    model_overrides: dict | None = None


class ProjectOut(ApiModel):
    id: str
    slug: str
    title: str
    owner_id: str
    owner_name: str
    kind: str
    kind_name: str
    entry: str
    profile_id: str | None
    profile_name: str | None
    venue: str | None
    stage: str
    model_overrides: dict | None
    counts: dict
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ kinds / house style


class KindSummary(BaseModel):
    slug: str
    name: str
    summary: str
    builtin: bool


class KindOut(KindSummary):
    files: dict[str, str]


class KindCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    summary: str = Field(default="", max_length=300)


class FileContent(BaseModel):
    content: str = Field(max_length=200_000)


# ------------------------------------------------------------------ usage


class UsageRow(BaseModel):
    key: str
    label: str
    calls: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    errors: int


class UsageSummary(BaseModel):
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    by_provider: list[UsageRow]
    by_purpose: list[UsageRow]
    by_project: list[UsageRow]
    recent: list[dict]
