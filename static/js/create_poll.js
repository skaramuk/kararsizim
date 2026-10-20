// Anket formunda seçenek alanlarını ekleme/çıkarma. JS kapalıyken 5 alan da görünür kalır;
// sunucu tarafı doğrulama her zaman esastır.
(function () {
  var MIN = 2;
  var MAX = 5;

  var list = document.getElementById("choices-list");
  if (!list) return;

  var rows = Array.prototype.slice.call(list.querySelectorAll(".choice-row"));
  var addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "btn btn-link add-choice";
  addButton.textContent = "+ Seçenek ekle";
  list.parentNode.appendChild(addButton);

  function visibleRows() {
    return rows.filter(function (row) { return !row.hidden; });
  }

  function refresh() {
    var count = visibleRows().length;
    addButton.hidden = count >= MAX;
    rows.forEach(function (row) {
      var remove = row.querySelector(".remove-choice");
      if (remove) remove.hidden = row.hidden || count <= MIN;
    });
    visibleRows().forEach(function (row, index) {
      row.querySelector("input").placeholder = (index + 1) + ". seçenek";
    });
  }

  rows.forEach(function (row, index) {
    var input = row.querySelector("input");
    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn-link remove-choice";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Seçeneği kaldır");
    remove.addEventListener("click", function () {
      input.value = "";
      row.hidden = true;
      list.appendChild(row); // gizlenen satır sona gider; gönderim sırası ekrandaki sırayla aynı kalır
      refresh();
    });
    row.appendChild(remove);
    if (index >= MIN && !input.value.trim()) row.hidden = true;
  });

  addButton.addEventListener("click", function () {
    var next = rows.filter(function (row) { return row.hidden; })[0];
    if (!next) return;
    list.insertBefore(next, null);
    next.hidden = false;
    next.querySelector("input").focus();
    refresh();
  });

  refresh();
})();
