"""Pydantic models for GlitchTip webhook payloads.

GlitchTip sends Slack-compatible webhook payloads when alerts are triggered.
"""

from pydantic import BaseModel, ConfigDict, Field


class GlitchTipField(BaseModel):
    """A field within a GlitchTip attachment.

    Fields contain metadata like project name, environment, and release.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Field name (e.g., 'project', 'environment')")
    value: str = Field(..., description="Field value")
    short: bool = Field(default=True, description="Whether to display in short format")


class GlitchTipAttachment(BaseModel):
    """An attachment within a GlitchTip alert.

    Contains the error details including title, link, and metadata fields.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Error title")
    title_link: str | None = Field(None, description="Link to the issue in GlitchTip")
    text: str | None = Field(None, description="Error message or stack trace preview")
    color: str | None = Field(None, description="Colour indicator (e.g., '#ff0000' for errors)")
    image_url: str | None = Field(None, description="Optional image URL")
    fields: list[GlitchTipField] = Field(default_factory=list, description="Metadata fields")

    def get_field_value(self, field_name: str) -> str | None:
        """Get the value of a field by name.

        :param field_name: The field title to look up.
        :returns: The field value or None if not found.
        """
        for field in self.fields:
            if field.title.lower() == field_name.lower():
                return field.value
        return None


class GlitchTipAlert(BaseModel):
    """The top-level GlitchTip webhook payload.

    This is the Slack-compatible format that GlitchTip sends.
    """

    model_config = ConfigDict(extra="ignore")

    alias: str | None = Field(None, description="Optional alias for the alert")
    text: str | None = Field(None, description="Main alert text")
    attachments: list[GlitchTipAttachment] = Field(
        default_factory=list, description="Alert attachments containing error details"
    )


class WebhookResponse(BaseModel):
    """Response model for webhook endpoints."""

    status: str = Field(..., description="Status of the webhook processing")
    message: str = Field(..., description="Human-readable message")
