"""Evaluation and routing models for LLM Router Evaluation.

Tables:
- routing_configs: Per-step routing configuration
- evaluation_datasets: Collections of prompt pairs
- evaluation_samples: Individual prompts within a dataset
- evaluation_results: Judge evaluation results
- evaluation_consensus: Consensus results per sample
- routing_decisions: Runtime routing choices
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.models.base import Base


class RoutingMode(StrEnum):
    FIXED = "fixed"
    DYNAMIC = "dynamic"


class DatasetStatus(StrEnum):
    PENDING_EVALUATION = "pending_evaluation"
    EVALUATED = "evaluated"
    CALIBRATED = "calibrated"


class JudgeType(StrEnum):
    LLM = "llm"
    HUMAN = "human"


class Preference(StrEnum):
    STRONG_WINS = "strong_wins"
    WEAK_WINS = "weak_wins"
    TIE = "tie"


class RoutingConfig(Base):
    __tablename__ = "routing_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step = Column(String(50), nullable=False, unique=True)
    mode = Column(String(10), nullable=False, default=RoutingMode.FIXED)
    strong_model = Column(String(100))
    weak_model = Column(String(100))
    threshold = Column(Float, default=0.5)
    enabled = Column(Boolean, default=False)
    classifier_version = Column(String(50))
    calibrated_at = Column(DateTime(timezone=True))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step = Column(String(50), nullable=False)
    name = Column(String(200))
    status = Column(String(20), nullable=False, default=DatasetStatus.PENDING_EVALUATION)
    sample_count = Column(Integer, nullable=False, default=0)
    strong_model = Column(String(100), nullable=False)
    weak_model = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    samples = relationship(
        "EvaluationSample", back_populates="dataset", cascade="all, delete-orphan"
    )


class EvaluationSample(Base):
    __tablename__ = "evaluation_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(
        Integer, ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    prompt_text = Column(Text, nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    strong_output = Column(Text)
    weak_output = Column(Text)
    strong_tokens = Column(Integer)
    weak_tokens = Column(Integer)
    strong_cost = Column(Float)
    weak_cost = Column(Float)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    dataset = relationship("EvaluationDataset", back_populates="samples")
    results = relationship(
        "EvaluationResult", back_populates="sample", cascade="all, delete-orphan"
    )
    consensus = relationship(
        "EvaluationConsensus", back_populates="sample", uselist=False, cascade="all, delete-orphan"
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(
        Integer, ForeignKey("evaluation_samples.id", ondelete="CASCADE"), nullable=False
    )
    judge_model = Column(String(100), nullable=False)
    judge_type = Column(String(10), nullable=False)
    preference = Column(String(20), nullable=False)
    critiques = Column(JSONB, nullable=False)
    reasoning = Column(Text)
    position_order = Column(String(20))  # 'strong_first' or 'weak_first'
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    sample = relationship("EvaluationSample", back_populates="results")


class EvaluationConsensus(Base):
    __tablename__ = "evaluation_consensus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(
        Integer,
        ForeignKey("evaluation_samples.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    consensus_preference = Column(String(20), nullable=False)
    agreement_rate = Column(Float)
    dimension_verdicts = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    sample = relationship("EvaluationSample", back_populates="consensus")


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step = Column(String(50), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    complexity_score = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    model_selected = Column(String(100), nullable=False)
    strong_model = Column(String(100), nullable=False)
    weak_model = Column(String(100), nullable=False)
    cost_actual = Column(Float)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (Index("idx_routing_decisions_step_created", "step", "created_at"),)
