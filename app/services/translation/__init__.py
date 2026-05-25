"""Translation service package.

The actual implementation lives in ``_impl`` (the historical
``app/translation_service.py``). This package re-exports its public surface so
callers can ``from app.services.translation import get_translation_service``.
"""

from ._impl import (  # noqa: F401
    TranslationCache,
    TranslationQueue,
    GoogleTranslateService,
    get_translation_service,
)
