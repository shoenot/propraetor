from django.apps import AppConfig


class PropraetorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "propraetor"

    def ready(self):
        from propraetor.activity import connect_signals

        connect_signals()