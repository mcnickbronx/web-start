/* Общее для админки всех модулей (подключает templates/admin/base_site.html ядра).
 *
 * Панель фильтров списка сворачивается щелчком по заголовку «Фильтр»; свёрнута она или нет,
 * браузер помнит для всех списков. Подсказки в фильтре и полях со связью (Select2): при открытии
 * курсор сразу в поле поиска, иначе первая набранная буква теряется.
 */
(function () {
  var KEY = "admin-filter-collapsed";

  document.addEventListener("DOMContentLoaded", function () {
    var panel = document.getElementById("changelist-filter");
    var title = panel && panel.querySelector(":scope > h2");
    if (title) {
      panel.classList.toggle("is-collapsed", localStorage.getItem(KEY) === "1");
      title.addEventListener("click", function () {
        var isCollapsed = panel.classList.toggle("is-collapsed");
        localStorage.setItem(KEY, isCollapsed ? "1" : "0");
      });
    }

    // jQuery в админке есть только на страницах с такими полями
    if (window.django && django.jQuery) {
      django.jQuery(document).on("select2:open", function () {
        var search = document.querySelector(".select2-container--open .select2-search__field");
        if (search) { search.focus(); }
      });
    }
  });
})();
