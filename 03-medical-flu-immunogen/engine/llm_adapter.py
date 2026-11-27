from abc import ABC, abstractmethod
from dataclasses import dataclass

from .capsules import EvidenceCapsule


@dataclass(frozen=True)
class Citation:
    evidence_id: str
    dataset_version: str
    text: str


class BaseLLMClient(ABC):
    # TODO(zicheng): plug in LLM provider
    @abstractmethod
    def assemble(self, query: str, records: list[EvidenceCapsule]) -> list[Citation]:
        """Return candidate quotations. The caller independently audits every item."""


class OfflineClient(BaseLLMClient):
    def assemble(self, query, records):
        return [Citation(*r.key, r.raw_snippet) for r in records]
