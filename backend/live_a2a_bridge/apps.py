from django.apps import AppConfig


class LiveA2ABridgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'live_a2a_bridge'
    verbose_name = 'Live API to A2A Worker Bridge'

    def ready(self):
        """Initialize the Live API + A2A bridge services"""
        pass
