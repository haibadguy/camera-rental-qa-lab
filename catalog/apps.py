from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CatalogConfig(AppConfig):
    name = "catalog"

    def ready(self):
        from .roles import create_operation_groups

        post_migrate.connect(create_operation_groups, sender=self)
