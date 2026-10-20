// "Bağlantıyı kopyala" düğmesi. JS ya da Clipboard API yoksa düğme gizli kalır;
// adres çubuğundaki bağlantı zaten paylaşılabilir.
(function () {
  var button = document.querySelector("[data-copy-link]");
  if (!button) return;
  var status = document.querySelector(".copy-link-status");
  var timer = null;

  function say(message) {
    if (!status) return;
    status.textContent = message;
    clearTimeout(timer);
    timer = setTimeout(function () { status.textContent = ""; }, 2500);
  }

  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "absolute";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (error) { ok = false; }
    document.body.removeChild(area);
    return ok;
  }

  var hasModernApi = !!(navigator.clipboard && navigator.clipboard.writeText);
  var hasLegacyApi = !!(document.queryCommandSupported && document.queryCommandSupported("copy"));
  if (!hasModernApi && !hasLegacyApi) return;
  button.hidden = false;

  button.addEventListener("click", function () {
    // Sorgu parametresi ve #parça olmadan temiz bağlantı
    var url = location.origin + location.pathname;
    var done = function () { say("Bağlantı kopyalandı ✓"); };
    var failed = function () { say("Kopyalanamadı; adres çubuğundan kopyalayabilirsin."); };

    if (hasModernApi) {
      navigator.clipboard.writeText(url).then(done, function () {
        if (legacyCopy(url)) done(); else failed();
      });
    } else if (legacyCopy(url)) {
      done();
    } else {
      failed();
    }
  });
})();
