from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class TextMessageContent(BaseModel):
    body: str

class WhatsAppMessageDetail(BaseModel):
    id: str
    from_: str = Field(..., alias="from")
    timestamp: str
    type: str
    text: Optional[TextMessageContent] = None

class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: Optional[List[dict]] = None
    messages: Optional[List[WhatsAppMessageDetail]] = None

class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str

class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]

class WhatsAppWebhookPayload(BaseModel):
    object: str
    entry: List[WhatsAppEntry]

class MatchDetail(BaseModel):
    contact_id: int
    name: str
    role: str
    confidence: float
    reasoning: str

class AgentResponse(BaseModel):
    analysis: str
    matches: List[MatchDetail]
    match_quality: Literal["good", "weak", "none"]
    clarification_question: Optional[str] = None


class ContactWrite(BaseModel):
    """Editable fields for manually adding/updating a contact from the
    dashboard. Excludes system-managed columns (id, contact_id, created_at/
    updated_at, and the intros_made/deals_closed counters the app itself
    increments)."""
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    sector: Optional[str] = None
    specialty: Optional[str] = None
    location: Optional[str] = None
    seniority: Optional[str] = None
    expertise_tags: Optional[str] = None
    can_help_with: Optional[str] = None
    looking_for: Optional[str] = None
    relationship_strength: Optional[int] = Field(default=None, ge=1, le=5)
    how_alex_knows_them: Optional[str] = None
    is_vip: bool = False
    preferred_contact_channel: Optional[str] = None
    comment: Optional[str] = None
