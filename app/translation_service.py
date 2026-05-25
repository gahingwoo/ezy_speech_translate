"""Backwards-compatible shim.

The translation service has moved to :mod:`app.services.translation`. This
module remains so that any external code importing
``app.translation_service`` (or ``from .translation_service import ...``)
keeps working.
"""

from app.services.translation import (  # noqa: F401
    TranslationCache,
    TranslationQueue,
    GoogleTranslateService,
    get_translation_service,
)
