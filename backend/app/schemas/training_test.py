"""Training certification MCQ — questions + submit result."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrainingTestQuestionPublic(BaseModel):
    id: int
    question: str
    options: dict[str, str]


class TrainingTestSubmitBody(BaseModel):
    answers: dict[str, str] = Field(
        ...,
        description="Map of question id (string) to answer letter a|b|c|d",
    )


class TrainingTestResultPublic(BaseModel):
    score: int
    total_questions: int
    percent: int
    passed: bool
    pass_mark_percent: int = 60
    attempted_at: datetime
    training_completed: bool = Field(
        default=False,
        description="True when server set users.training_status=completed (refresh JWT via sync-identity)",
    )


class MarkTrainingDayBody(BaseModel):
    day_number: int = Field(ge=1, le=31, description="Must match a row in ``training_videos``")
