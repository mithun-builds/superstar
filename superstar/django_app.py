"""Django AppConfig for SuperStar core.

This is the only piece of Django glue inside the `superstar/` package — its
job is to call `load_plugins(settings.SUPERSTAR_CONFIG_DIR)` at startup.

Register this app via INSTALLED_APPS as `superstar.django_app.SuperStarCoreConfig`.
"""
from __future__ import annotations

import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class SuperStarCoreConfig(AppConfig):
    name = "superstar.django_app"
    label = "superstar_core"
    verbose_name = "SuperStar Core"

    def ready(self) -> None:
        # Late import: avoid pulling Django into the plugins package's import path.
        from superstar.plugins.loader import load_plugins

        try:
            loaded = load_plugins(settings.SUPERSTAR_CONFIG_DIR)
        except Exception:
            logger.exception("Plugin discovery failed at startup")
            raise
        logger.info("SuperStar startup: %d plugin(s) loaded.", len(loaded))
