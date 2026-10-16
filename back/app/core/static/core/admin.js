/* Общее для админки всех модулей (подключает templates/admin/base_site.html ядра).
 *
 * Подсказки в полях со связью на странице записи (autocomplete_fields, Select2): при открытии
 * курсор сразу в поле поиска, иначе первая набранная буква теряется. В фильтрах списка это делает
 * пакет django-admin-filter-kit.
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // jQuery в админке есть только на страницах с такими полями
    if (window.django && django.jQuery) {
      django.jQuery(document).on("select2:open", function () {
        var search = document.querySelector(".select2-container--open .select2-search__field");
        if (search) { search.focus(); }
      });
    }
  });
})();
