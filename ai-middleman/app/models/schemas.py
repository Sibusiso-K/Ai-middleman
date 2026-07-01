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
