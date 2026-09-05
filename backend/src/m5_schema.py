from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Literal

class AIDecision(BaseModel):
    decision: Literal["MATCH", "NO_MATCH", "AMBIGUOUS"]
    selected_candidate_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    missing_evidence: List[str] = []
    recommended_action: Literal["ACCEPT", "ESCALATE", "REQUEST_MORE_DATA"]

    @model_validator(mode='after')
    def validate_candidate_selection(self):
        if self.decision == "MATCH" and not self.selected_candidate_id:
            raise ValueError("selected_candidate_id MUST be provided when decision is MATCH")
        if self.decision in ["NO_MATCH", "AMBIGUOUS"] and self.selected_candidate_id is not None:
            raise ValueError("selected_candidate_id MUST be null when decision is not MATCH")
        return self