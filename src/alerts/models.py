"""Pydantic models for alert data."""

from pydantic import BaseModel, Field

from src.alerts.enums import AlertType


class AlertItem(BaseModel):
    """An item within an alert (e.g., a task, article, reading item)."""

    name: str = Field(..., description="Item name or title")
    url: str | None = Field(None, description="Optional link URL")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class AlertData(BaseModel):
    """Data for an alert to be sent."""

    alert_type: AlertType = Field(..., description="Type of alert")
    source_id: str = Field(..., description="Unique identifier for the source")
    title: str = Field(..., description="Alert title or header")
    items: list[AlertItem] = Field(default_factory=list, description="Items in the alert")


class AlertSendResult(BaseModel):
    """Result of sending alerts."""

    alerts_sent: int = Field(default=0, description="Number of alerts successfully sent")
    alerts_skipped: int = Field(default=0, description="Number of alerts skipped (already sent)")
    errors: list[str] = Field(default_factory=list, description="Error messages from failed sends")
