"""Source Collection Agent package.

Implements content collection only (no filtering / categorization / generation).
"""

from app.agents.source_collection.collector import SourceCollectionAgent
from app.agents.source_collection.types import CollectionResult, RawArticle

__all__ = ["SourceCollectionAgent", "RawArticle", "CollectionResult"]
