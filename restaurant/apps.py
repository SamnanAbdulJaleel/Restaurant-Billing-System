from django.apps import AppConfig


class RestaurantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'restaurant'
    verbose_name = 'Restaurant Management'

    def ready(self):
        import restaurant.models  # This ensures models are loaded
        return super().ready()
