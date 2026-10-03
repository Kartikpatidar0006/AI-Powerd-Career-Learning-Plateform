"""
Pydantic v2 schemas for interview-agent-service.

Provides request/response schemas for:
- Student-facing interview session responses with computed time remaining
- Interview question and answer turns
- Proctoring violation event creation and logging
- Internal service-to-service interview session creation
- Interview start, answer submission, and resume responses
- Dynamic LLM-generated questions and overall performance summary
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.interview import InterviewSessionStatus, ProctoringEventType


class InterviewTurnResponse(BaseModel):
    """Student and API response schema for an interview turn."""
    id: uuid.UUID
    session_id: uuid.UUID
    turn_number: int
    question_text: str
    question_context: dict[str, Any] | None = None
    answer_text: str | None = None
    answer_duration_seconds: float | None = None
    follow_up_of: uuid.UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewSessionResponse(BaseModel):
    """
    Student-facing response schema for an interview session.

    Excludes internal implementation details (e.g. detailed termination_reason)
    while exposing status, expiration details, violation count, and dynamic
    time_remaining_seconds.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    evaluation_id: uuid.UUID
    status: InterviewSessionStatus
    available_from: datetime
    expires_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    violation_count: int = 0
    termination_reason: str | None = None
    overall_performance_summary: dict[str, Any] | None = None
    created_at: datetime

    @computed_field
    @property
    def time_remaining_seconds(self) -> float:
        """
        Seconds remaining until the session expires.

        Returns 0.0 if the interview is completed, expired, or terminated.
        """
        if self.status in (
            InterviewSessionStatus.COMPLETED,
            InterviewSessionStatus.EXPIRED,
            InterviewSessionStatus.TERMINATED_VIOLATION,
        ):
            return 0.0

        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return max(0.0, (exp - now).total_seconds())

    model_config = ConfigDict(from_attributes=True)


class InterviewStartResponse(BaseModel):
    """Response returned when an interview is started, containing session and first question."""
    session: InterviewSessionResponse
    first_question: InterviewTurnResponse
    is_closing: bool = False

    # Top-level mirrored fields for backward-compatibility
    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    evaluation_id: uuid.UUID
    status: InterviewSessionStatus
    available_from: datetime
    expires_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    violation_count: int = 0
    termination_reason: str | None = None
    overall_performance_summary: dict[str, Any] | None = None
    created_at: datetime
    time_remaining_seconds: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class InterviewResumeResponse(BaseModel):
    """
    Response schema for GET /interview/sessions/{task_id}/resume.

    Contains the session details along with all completed and current turns
    so the client can reconstruct interview state and progress.
    """
    session: InterviewSessionResponse
    turns: list[InterviewTurnResponse] = Field(default_factory=list)

    # Root-level mirrored fields for convenience
    id: uuid.UUID
    user_id: uuid.UUID
    task_id: uuid.UUID
    evaluation_id: uuid.UUID
    status: InterviewSessionStatus
    available_from: datetime
    expires_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    violation_count: int = 0
    termination_reason: str | None = None
    overall_performance_summary: dict[str, Any] | None = None
    created_at: datetime
    time_remaining_seconds: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class SubmitAnswerRequest(BaseModel):
    """Request payload for submitting an answer to the current unanswered turn."""
    answer_text: str = Field(..., min_length=1, description="Candidate's technical answer text")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Time taken to compose answer in seconds")


class AnswerSubmissionResponse(BaseModel):
    """
    Response returned when an answer is submitted.

    Includes the updated session, the answered turn, and the next question
    (or closing turn if the interview turn limit was reached).
    """
    session: InterviewSessionResponse
    answered_turn: InterviewTurnResponse
    next_turn: InterviewTurnResponse
    is_closing: bool = False
    status: str
    overall_performance_summary: dict[str, Any] | None = None

    @computed_field
    @property
    def question(self) -> InterviewTurnResponse:
        """Alias for next_turn for flexible client consumption."""
        return self.next_turn

    model_config = ConfigDict(from_attributes=True)


class GeneratedQuestion(BaseModel):
    """Structure produced by the LLM interview agent for a question turn."""
    title: str = Field(..., description="Short topic or question title")
    question_text: str = Field(..., description="The interview question or closing statement")
    question_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Targeted finding, skill context, or injection defense flags",
    )
    is_closing: bool = Field(default=False, description="True if this turn concludes the interview")


class OverallPerformanceSummary(BaseModel):
    """Final interview performance evaluation synthesized across all transcript turns."""
    communication_clarity: int = Field(ge=0, le=100)
    technical_depth: int = Field(ge=0, le=100)
    confidence_signals: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    summary: str
    key_strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)


class ProctoringEventCreate(BaseModel):
    """Request schema for logging client-side proctoring violation events."""
    event_type: ProctoringEventType
    turn_number_at_event: int | None = Field(
        default=None,
        description="Turn number during which the proctoring event was detected",
    )


class ProctoringEventResponse(BaseModel):
    """Response schema for recorded proctoring events."""
    id: uuid.UUID
    session_id: uuid.UUID
    event_type: ProctoringEventType
    timestamp: datetime
    turn_number_at_event: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ProctoringEventSubmissionResponse(BaseModel):
    """
    Response schema for POST /interview/sessions/{task_id}/proctoring-event.

    Signals violation progression and termination to the student frontend.
    """
    event: ProctoringEventResponse
    session_status: InterviewSessionStatus
    violation_count: int
    max_violations: int = 3
    terminated: bool = False
    termination_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InternalCreateSessionRequest(BaseModel):
    """
    Internal request schema for POST /internal/interview/create-session.

    Invoked by Agent 3 (evaluator-agent-service) or workflow orchestrator
    when an evaluation is completed and an interview is unlocked.
    """
    task_id: uuid.UUID
    user_id: uuid.UUID
    evaluation_id: uuid.UUID
    evaluation_context: dict[str, Any] | None = Field(
        default=None,
        description="Optional Agent 3 findings context passed at creation time to avoid network calls",
    )
