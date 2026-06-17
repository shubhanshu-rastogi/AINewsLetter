"""Agent foundation (placeholder).

Defines the contract every agent will implement. NO agent logic is implemented
yet - this only establishes the interface and naming so the workflow layer can
be wired up later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base for all agents in the pipeline.

    Concrete agents (Source Collection, Relevance, Categorization, Fact
    Checking, Newsletter Writer, LinkedIn Post, Visual Generation, Editorial
    Review, Feedback Processing, Publishing) will subclass this.
    """

    name: str = "base_agent"

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent against the workflow state and return updates.

        Not implemented in the foundation phase.
        """
        raise NotImplementedError
