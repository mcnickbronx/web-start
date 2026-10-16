"""Фильтр списка в админке с поиском по связи: справочник большой — списком в панели не помещается."""
from admin_auto_filters.filters import AutocompleteFilter as PackageAutocompleteFilter


class AutocompleteFilter(PackageAutocompleteFilter):
    """Фильтр пакета admin_auto_filters: `title` и `field_name` связи, у админки справочника — `search_fields`.

    Пакет (последний выпуск — 2021) берёт записи справочника через дескриптор связи, а в новых Django
    его `get_queryset()` требует `instance` — список заявок падал. Здесь записи берутся напрямую.
    """

    @staticmethod
    def get_queryset_for_field(model, name):
        return model._meta.get_field(name).related_model._default_manager.all()
