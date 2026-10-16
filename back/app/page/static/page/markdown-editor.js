/* Редактор Toast UI для полей Markdown в админке (page/widgets.py).
 *
 * Параметры берутся из data-атрибутов textarea:
 *   data-markdown-editor — поднять здесь редактор;
 *   data-upload-url      — куда загружать картинки из вставки и перетаскивания.
 *
 * Редактор живёт в своём <div>. Textarea прячем, но оставляем в форме: форма отправляет
 * именно её значение, поэтому держим его актуальным на каждое изменение и перед отправкой.
 * Загрузка идёт POST-запросом в админку, ему нужен CSRF-токен формы. Тема редактора — как у админки.
 */
(function () {
  function csrfToken(field) {
    var form = field.closest("form");
    var input = form && form.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function initField(field) {
    if (field.dataset.editorReady) { return; }
    field.dataset.editorReady = "1";
    field.style.display = "none";

    var host = document.createElement("div");
    host.style.flex = "1 1 auto";
    host.style.minWidth = "0";
    field.parentNode.insertBefore(host, field.nextSibling);

    var editor = new toastui.Editor({
      el: host,
      height: "560px",
      initialEditType: "wysiwyg",
      previewStyle: "vertical",
      language: "ru-RU",
      // По умолчанию редактор отправляет статистику в Google Analytics — не нужно
      usageStatistics: false,
      initialValue: field.value || "",
      hooks: {
        addImageBlobHook: function (blob, callback) {
          var body = new FormData();
          body.append("image", blob, blob.name || "image.png");
          fetch(field.dataset.uploadUrl, {
            method: "POST",
            body: body,
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrfToken(field) }
          })
            .then(function (response) {
              return response.json()
                .catch(function () { return {}; })
                .then(function (data) { return { ok: response.ok, data: data }; });
            })
            .then(function (result) {
              if (!result.ok || !result.data.url) {
                alert(result.data.message || "Не удалось загрузить картинку");
                return;
              }
              callback(result.data.url, blob.name || "");
            })
            .catch(function () { alert("Не удалось загрузить картинку"); });
          return false;
        }
      }
    });

    // Тема админки Django — data-theme на <html>: dark, light или auto (как в системе); её меняет
    // переключатель в шапке. Редактор следует за ней: его тёмная тема — класс toastui-editor-dark
    var root = host.querySelector(".toastui-editor-defaultUI");
    var systemDark = window.matchMedia("(prefers-color-scheme: dark)");
    function syncTheme() {
      var theme = document.documentElement.dataset.theme;
      root.classList.toggle("toastui-editor-dark", theme === "dark" || (theme !== "light" && systemDark.matches));
    }
    syncTheme();
    new MutationObserver(syncTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    systemDark.addEventListener("change", syncTheme);

    function syncField() { field.value = editor.getMarkdown(); }
    editor.on("change", syncField);
    var form = field.closest("form");
    if (form) { form.addEventListener("submit", syncField); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("textarea[data-markdown-editor]").forEach(initField);
  });
})();
