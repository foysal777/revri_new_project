from django.apps import AppConfig


class ChatsystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatsystem'

    def ready(self):
        from .ai import register_signals, sync_all_products, vector_store, openai_client
        register_signals()

        if openai_client:
            try:
                chunks = vector_store.read().get('chunks', [])
                if not chunks:
                    sync_all_products()
            except Exception:
                pass
