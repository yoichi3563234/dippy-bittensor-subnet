from enum import Enum
from typing import Optional, Any, Dict

from pydantic import BaseModel, Field
import math

CREATIVITY_STEEPNESS = 8
CREATIVITY_THRESHOLD = 0.5

LLM_MODEL_SIZE_THRESHOLD = 0.75
LLM_MODEL_SIZE_STEEPNESS = 8
QUALITATIVE_SCORE_WEIGHT = 0.84  # weight of the qualitative score in the total score
LATENCY_SCORE_WEIGHT = 0.08  # weight of the latency score in the total score
VIBE_SCORE_WEIGHT = 0.08  # weight of the vibe score in the total score
COHERENCE_MINIMUM = 0.95


class StrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    @classmethod
    def from_string(cls, value: str):
        try:
            return cls(value.upper())
        except ValueError:
            raise ValueError(f"{value} is not a valid {cls.__name__}")


class StatusEnum(StrEnum):
    QUEUED = "QUEUED"
    PRECHECK = "PRECHECK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RUNNING = "RUNNING"


class Scores(BaseModel):
    total_score: float = Field(default=0, description="The total score of the evaluation")
    coherence_score: float = Field(default=0, description="The coherence score of the text")
    vibe_score: float = Field(default=0, description="The vibe score of the text")
    creativity_score: float = Field(default=0, description="The creativity score")
    qualitative_score: float = Field(default=0, description="The qualitative score of the text")
    llm_size_score: float = Field(default=0, description="The model_size score of the text")
    latency_score: float = Field(default=0, description="The latency score of the text")
    status: str = Field(default=StatusEnum.QUEUED, description="The current status of the scoring process")

    @staticmethod
    def adjusted_q_score(
        initial_score: float, creativity_score: float, threshold=CREATIVITY_THRESHOLD, steepness=CREATIVITY_STEEPNESS
    ):
        adjusted_score = initial_score / (1 + math.exp(-steepness * (creativity_score - threshold)))
        return adjusted_score

    @staticmethod
    def model_size_adjuster(
        model_size_score: float, threshold=LLM_MODEL_SIZE_THRESHOLD, steepness=LLM_MODEL_SIZE_STEEPNESS
    ):
        if model_size_score < threshold:
            # Exponential penalty that increases as score drops below threshold
            penalty_multiplier = pow(model_size_score / threshold, steepness)
            return penalty_multiplier

        return 1

    def from_response(self, response: Dict[str, Any]):
        if response is None or len(response) < 1:
            self.total_score = 0
            return self
        self.llm_size_score = response.get("model_size_score", 0)
        self.creativity_score = response.get("creativity_score", 0)
        self.qualitative_score = response.get("qualitative_score", 0)
        self.vibe_score = response.get("vibe_score", 0)
        self.coherence_score = response.get("coherence_score", 0)
        self.latency_score = response.get("latency_score", 0)
        return self

    def calculate_total_score(self, adjust_coherence: bool = False) -> float:
        q_score = self.adjusted_q_score(self.qualitative_score, self.creativity_score)
        total_score = 0
        total_score += QUALITATIVE_SCORE_WEIGHT * q_score
        total_score += LATENCY_SCORE_WEIGHT * self.latency_score
        total_score += VIBE_SCORE_WEIGHT * self.vibe_score
        self.coherence_score = 1 if self.coherence_score >= COHERENCE_MINIMUM else 0
        total_score = total_score * self.coherence_score
        multiplier = self.model_size_adjuster(self.llm_size_score)
        total_score = total_score * multiplier
        return total_score
