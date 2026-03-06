(function () {
  function initTypeahead(form) {
    var input = form.querySelector('input[name="q"]');
    if (!input) return;
    if (input.dataset.typeaheadBound === "1") return;
    input.dataset.typeaheadBound = "1";

    var menu = document.createElement("div");
    menu.className = "typeahead-menu";
    menu.hidden = true;
    if (window.getComputedStyle(form).position === "static") {
      form.style.position = "relative";
    }
    form.appendChild(menu);

    var items = [];
    var activeIndex = -1;
    var timer = null;
    var controller = null;

    function hideMenu() {
      menu.hidden = true;
      menu.innerHTML = "";
      items = [];
      activeIndex = -1;
    }

    function renderMenu(suggestions) {
      if (!suggestions || suggestions.length === 0) {
        hideMenu();
        return;
      }
      items = suggestions;
      activeIndex = -1;
      menu.innerHTML = suggestions
        .map(function (s, i) {
          var title = String(s.title || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          var ascl = String(s.ascl_id || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          // snippet is pre-formatted HTML from Typesense with <mark> tags
          var snippet = s.snippet || "";
          var snippetHtml = snippet
            ? '<span class="typeahead-snippet">' + snippet + "</span>"
            : "";
          return (
            '<a class="typeahead-item" data-idx="' + i + '" href="' + s.url + '">' +
            '<span class="typeahead-title">' + title + "</span>" +
            '<span class="typeahead-meta">ascl:' + ascl + "</span>" +
            snippetHtml +
            "</a>"
          );
        })
        .join("");
      menu.hidden = false;
    }

    function setActive(nextIndex) {
      var nodes = menu.querySelectorAll(".typeahead-item");
      nodes.forEach(function (n) { n.classList.remove("active"); });
      if (nodes.length === 0) return;
      activeIndex = nextIndex;
      if (activeIndex < 0) activeIndex = nodes.length - 1;
      if (activeIndex >= nodes.length) activeIndex = 0;
      nodes[activeIndex].classList.add("active");
    }

    function fetchSuggestions(q) {
      if (controller) controller.abort();
      controller = new AbortController();
      fetch("/search/suggest?q=" + encodeURIComponent(q) + "&limit=8", { signal: controller.signal })
        .then(function (r) { return r.ok ? r.json() : { suggestions: [] }; })
        .then(function (data) {
          renderMenu(data.suggestions || []);
        })
        .catch(function () {});
    }

    input.addEventListener("input", function () {
      var q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) {
        hideMenu();
        return;
      }
      timer = setTimeout(function () { fetchSuggestions(q); }, 150);
    });

    input.addEventListener("keydown", function (ev) {
      if (menu.hidden) return;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        setActive(activeIndex + 1);
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        setActive(activeIndex - 1);
      } else if (ev.key === "Enter" && activeIndex >= 0) {
        var nodes = menu.querySelectorAll(".typeahead-item");
        if (nodes[activeIndex]) {
          ev.preventDefault();
          window.location.assign(nodes[activeIndex].getAttribute("href"));
        }
      } else if (ev.key === "Escape") {
        hideMenu();
      }
    });

    menu.addEventListener("mousedown", function (ev) {
      var target = ev.target.closest(".typeahead-item");
      if (!target) return;
      ev.preventDefault();
      window.location.assign(target.getAttribute("href"));
    });

    input.addEventListener("blur", function () {
      setTimeout(hideMenu, 120);
    });
    input.addEventListener("focus", function () {
      if (items.length > 0) menu.hidden = false;
    });
  }

  function initAuthorTypeahead(form) {
    var input = form.querySelector('input[name="search"]');
    if (!input) return;
    if (input.dataset.typeaheadBound === "1") return;
    input.dataset.typeaheadBound = "1";

    var menu = document.createElement("div");
    menu.className = "typeahead-menu";
    menu.hidden = true;
    if (window.getComputedStyle(form).position === "static") {
      form.style.position = "relative";
    }
    form.appendChild(menu);

    var items = [];
    var activeIndex = -1;
    var timer = null;
    var controller = null;

    function hideMenu() {
      menu.hidden = true;
      menu.innerHTML = "";
      items = [];
      activeIndex = -1;
    }

    function renderMenu(suggestions) {
      if (!suggestions || suggestions.length === 0) {
        hideMenu();
        return;
      }
      items = suggestions;
      activeIndex = -1;
      menu.innerHTML = suggestions
        .map(function (name, i) {
          var safe = String(name || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          return (
            '<button type="button" class="typeahead-item typeahead-author" data-idx="' + i + '">' +
            '<span class="typeahead-title">' + safe + "</span>" +
            "</button>"
          );
        })
        .join("");
      menu.hidden = false;
    }

    function setActive(nextIndex) {
      var nodes = menu.querySelectorAll(".typeahead-item");
      nodes.forEach(function (n) { n.classList.remove("active"); });
      if (nodes.length === 0) return;
      activeIndex = nextIndex;
      if (activeIndex < 0) activeIndex = nodes.length - 1;
      if (activeIndex >= nodes.length) activeIndex = 0;
      nodes[activeIndex].classList.add("active");
    }

    function fetchSuggestions(q) {
      if (controller) controller.abort();
      controller = new AbortController();
      fetch("/search/author_suggest?q=" + encodeURIComponent(q) + "&limit=8", { signal: controller.signal })
        .then(function (r) { return r.ok ? r.json() : { suggestions: [] }; })
        .then(function (data) {
          renderMenu(data.suggestions || []);
        })
        .catch(function () {});
    }

    function submitWithName(name) {
      input.value = name;
      form.submit();
    }

    input.addEventListener("input", function () {
      var q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) {
        hideMenu();
        return;
      }
      timer = setTimeout(function () { fetchSuggestions(q); }, 150);
    });

    input.addEventListener("keydown", function (ev) {
      if (menu.hidden) return;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        setActive(activeIndex + 1);
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        setActive(activeIndex - 1);
      } else if (ev.key === "Enter" && activeIndex >= 0) {
        ev.preventDefault();
        submitWithName(items[activeIndex]);
      } else if (ev.key === "Escape") {
        hideMenu();
      }
    });

    menu.addEventListener("mousedown", function (ev) {
      var target = ev.target.closest(".typeahead-item");
      if (!target) return;
      ev.preventDefault();
      var idx = parseInt(target.getAttribute("data-idx"), 10);
      if (!Number.isNaN(idx) && items[idx]) submitWithName(items[idx]);
    });

    input.addEventListener("blur", function () {
      setTimeout(hideMenu, 120);
    });
    input.addEventListener("focus", function () {
      if (items.length > 0) menu.hidden = false;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('form[action="/search"]').forEach(initTypeahead);
    document.querySelectorAll('form[action="/code/cs_submit"]').forEach(initAuthorTypeahead);
  });
})();
