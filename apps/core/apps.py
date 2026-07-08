from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        from .audit import register_audited_models
        from .compat import apply_basecontext_copy_patch

        apply_basecontext_copy_patch()
        register_audited_models()
