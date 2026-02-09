"""Test factories for model creation.

Factory Boy factories for creating test instances of database models.
These factories provide consistent, realistic test data with support
for different states via traits.

Usage:
    from tests.factories import ContentFactory, SummaryFactory, DigestFactory

    # Basic usage
    content = ContentFactory()

    # With traits
    pending_content = ContentFactory(pending=True)
    content_with_audio = ContentFactory(with_audio=True)

    # Building without database (dict only)
    content_data = ContentFactory.build()

    # Creating in database (requires session fixture)
    content = ContentFactory.create()
"""

from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.podcast import PodcastFactory, PodcastScriptRecordFactory
from tests.factories.summary import SummaryFactory

__all__ = [
    "ContentFactory",
    "SummaryFactory",
    "DigestFactory",
    "PodcastScriptRecordFactory",
    "PodcastFactory",
]
