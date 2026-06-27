"""
handlers/__init__.py
--------------------
Central handler registration.
All handler modules are imported and registered here in the correct order.
Order matters — more specific filters should be registered before general ones.
"""

from .start import register_start_handlers
from .admin import register_admin_handlers
from .user import register_user_handlers
from .media import register_media_handlers


def register_handlers(app, db, queue_manager):
    """Register all bot handlers."""

    # 1. Start/help — always first (handles unauthorized users gracefully)
    register_start_handlers(app, db, queue_manager)

    # 2. Admin commands — before user commands (owner also gets /stats etc.)
    register_admin_handlers(app, db, queue_manager)

    # 3. User commands — /history, /stats, /translate
    register_user_handlers(app, db, queue_manager)

    # 4. Media handlers — last (catches audio/video/voice/document messages)
    register_media_handlers(app, db, queue_manager)
  
