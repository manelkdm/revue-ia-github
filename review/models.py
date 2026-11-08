"""Contrats validés à l'entrée, à la sortie du modèle et avant publication."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(StrictModel):
    severity: Literal["info", "low", "medium", "high", "critical"]
    title: str = Field(max_length=200)
    evidence: str = Field(max_length=1500)
    recommendation: str = Field(max_length=1500)
    file: str | None = Field(default=None, max_length=500)
    line: int | None = Field(default=None, ge=1)
    source: Literal["llm", "tool"] = "llm"


class Criterion(StrictModel):
    id: str = Field(max_length=80)
    text: str = Field(max_length=1000)
    status: Literal["supported", "not_met", "unknown"] = "unknown"
    evidence: str = Field(default="", max_length=1500)


class AgentResult(StrictModel):
    agent: int = Field(ge=1, le=7)
    status: Literal["complete", "incomplete"]
    summary: str = Field(max_length=3000)
    findings: list[Finding] = Field(default_factory=list, max_length=160)
    criteria: list[Criterion] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    duplicate_groups: list[list[str]] = Field(default_factory=list, max_length=160)


class ToolResult(StrictModel):
    status: Literal["passed", "failed", "error", "not_run"]
    findings: list[Finding] = Field(default_factory=list, max_length=300)
    details: str = Field(default="", max_length=2000)
    total_findings: int = Field(default=0, ge=0)


class Evidence(StrictModel):
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    generated_at: str
    tools: dict[str, ToolResult]
    coverage_percent: float | None = Field(default=None, ge=0, le=100)
    tests_run: int = Field(default=0, ge=0)
    tests_failed: int = Field(default=0, ge=0)
    tests_skipped: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def coherent_counts(self):
        if self.tests_failed + self.tests_skipped > self.tests_run:
            raise ValueError("Nombre de tests échoués ou ignorés incohérent")
        return self


class Issue(StrictModel):
    number: int = Field(gt=0)
    title: str
    body: str


class Context(StrictModel):
    repository: str
    pr: int = Field(gt=0)
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    pr_title: str
    pr_body: str = ""
    issue: Issue | None = None
    diff: str
    standards: str = ""
    evidence: Evidence | None = None
    warnings: list[str] = Field(default_factory=list)
    demo: bool = False


class Review(StrictModel):
    schema_version: Literal[3] = 3
    forge: Literal["github"] = "github"
    run_id: str
    created_at: str
    model: str
    demo: bool
    repository: str
    pr: int
    head_sha: str
    base_sha: str
    source_digest: str
    input_digest: str
    results: list[AgentResult] = Field(min_length=7, max_length=7)
    finding_groups: list[list[str]]
    decision: Literal["corrections_recommandees", "revue_humaine_requise", "pret_pour_validation_humaine"]
    reasons: list[str]
    tools: dict[str, ToolResult]
    coverage_percent: float | None
    warnings: list[str]
    human_approval_required: Literal[True] = True

    @model_validator(mode="before")
    @classmethod
    def supported_version(cls, data):
        if isinstance(data, dict) and data.get("schema_version") != 3:
            raise ValueError("Version de rapport incompatible ; relancez la revue avec le schéma 3.")
        return data

    @model_validator(mode="after")
    def seven_agents(self):
        if [result.agent for result in self.results] != list(range(1, 8)):
            raise ValueError("Le rapport doit contenir les sept agents dans l'ordre")
        from .findings import catalog, validate_groups
        validate_groups(catalog(self.results, self.tools), self.finding_groups)
        return self
