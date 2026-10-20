// Oy formunu fetch ile gönderir ve sayfayı yenilemeden sonuç çubuklarını çizer.
// JS çalışmazsa ya da istek başarısız olursa form normal şekilde gönderilir.
// Sonuç yapısı templates/partials/results.html ile aynı olmalı.
(function () {
  var form = document.querySelector(".vote-form");
  if (!form || !window.fetch) return;

  var lastClicked = null;
  form.addEventListener("click", function (event) {
    var button = event.target.closest("button[name=choice]");
    if (button) lastClicked = button;
  });

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : "";
  }

  function csrfToken() {
    var input = form.querySelector("input[name=csrfmiddlewaretoken]");
    return getCookie("csrftoken") || (input ? input.value : "");
  }

  function setBusy(busy) {
    form.querySelectorAll("button").forEach(function (button) { button.disabled = busy; });
  }

  function showError(message) {
    var box = form.querySelector(".vote-error");
    if (!box) {
      box = document.createElement("p");
      box.className = "field-error vote-error";
      box.setAttribute("role", "alert");
      form.appendChild(box);
    }
    box.textContent = message;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function buildResults(data) {
    var section = el("section", "results");
    section.setAttribute("aria-label", "Sonuçlar");
    var list = el("ul", "result-list");
    var fills = [];

    data.results.forEach(function (item) {
      var mine = item.id === data.voted_choice_id;
      var row = el("li", "result-item" + (mine ? " is-mine" : ""));

      var head = el("div", "result-head");
      var text = el("span", "result-text", item.text);
      if (mine) {
        text.appendChild(document.createTextNode(" "));
        text.appendChild(el("span", "mine-badge", "✓ Senin oyun"));
      }
      head.appendChild(text);
      head.appendChild(el("span", "result-figures", item.count + " oy · %" + item.percent));

      var bar = el("div", "result-bar");
      var fill = el("div", "result-fill");
      fill.style.width = "0%";
      fills.push([fill, item.percent]);
      bar.appendChild(fill);

      row.appendChild(head);
      row.appendChild(bar);
      list.appendChild(row);
    });

    section.appendChild(list);
    section.appendChild(el("p", "result-total", "Toplam " + data.total + " oy"));

    // Çubuklar 0'dan hedef genişliğe CSS geçişiyle uzar.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        fills.forEach(function (pair) { pair[0].style.width = pair[1] + "%"; });
      });
    });
    return section;
  }

  function showResults(data) {
    var section = buildResults(data);
    var existing = document.querySelector(".results");
    if (existing) {
      existing.replaceWith(section);
      form.remove();
    } else {
      form.replaceWith(section);
    }
    var total = document.querySelector("[data-vote-total]");
    if (total) total.textContent = data.total + " oy";
  }

  function fallbackSubmit(button) {
    // fetch kullanılamadı: seçimi gizli alanla taşıyıp normal gönderime düş.
    var hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "choice";
    hidden.value = button.value;
    form.appendChild(hidden);
    form.submit();
  }

  form.addEventListener("submit", function (event) {
    var button = event.submitter || lastClicked;
    if (!button) return; // seçim belirlenemedi: normal gönderim
    event.preventDefault();
    setBusy(true);

    fetch(form.action, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrfToken(),
      },
      body: new URLSearchParams({ choice: button.value }).toString(),
    })
      .then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      })
      .then(function (result) {
        if (result.ok && result.data.ok) {
          showResults(result.data);
        } else {
          showError(result.data.error || "Oy kaydedilemedi.");
          setBusy(false);
        }
      })
      .catch(function () {
        fallbackSubmit(button);
      });
  });
})();
