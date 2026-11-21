from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope[EventData: BaseModel](BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    event_type: str = Field(alias="eventType")
    occurred_at: datetime = Field(alias="occurredAt")
    source: str
    correlation_id: UUID = Field(alias="correlationId")
    causation_id: UUID | None = Field(default=None, alias="causationId")
    subject: str
    version: str = "1"
    data: EventData
