/* =========================================================================
   main.js — progressive enhancement only. The site is fully usable without JS.
   Handles: mobile nav toggle, dismissible announcement bar, share buttons,
   current-year stamp, and honest no-endpoint form guarding.
   ========================================================================= */
(function () {
  "use strict";

  /* ---- Mobile nav toggle ---- */
  var navToggle = document.querySelector("[data-nav-toggle]");
  var nav = document.getElementById("primary-nav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    // Close the menu when a link is tapped (mobile).
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a") && nav.classList.contains("is-open")) {
        nav.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ---- Dismissible announcement bar (remembers choice per session) ---- */
  var bar = document.querySelector("[data-announce]");
  var dismiss = document.querySelector("[data-announce-dismiss]");
  if (bar && sessionStorage.getItem("oss-announce-dismissed") === "1") {
    bar.hidden = true;
  }
  if (bar && dismiss) {
    dismiss.addEventListener("click", function () {
      bar.hidden = true;
      try { sessionStorage.setItem("oss-announce-dismissed", "1"); } catch (e) {}
    });
  }

  /* ---- Current year in footer ---- */
  var years = document.querySelectorAll("[data-year]");
  var yr = String(new Date().getFullYear());
  for (var i = 0; i < years.length; i++) years[i].textContent = yr;

  /* ---- Share buttons ---- */
  var shareBtns = document.querySelectorAll("[data-share]");
  var pageUrl = window.location.href;
  var shareTitle = document.title;
  for (var s = 0; s < shareBtns.length; s++) {
    shareBtns[s].addEventListener("click", function (e) {
      var kind = this.getAttribute("data-share");
      var u = encodeURIComponent(pageUrl);
      var t = encodeURIComponent(shareTitle);
      var target = "";
      if (kind === "x") target = "https://twitter.com/intent/tweet?url=" + u + "&text=" + t;
      else if (kind === "facebook") target = "https://www.facebook.com/sharer/sharer.php?u=" + u;
      else if (kind === "email") { window.location.href = "mailto:?subject=" + t + "&body=" + u; return; }
      else if (kind === "copy") {
        e.preventDefault();
        var self = this;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(pageUrl).then(function () { flash(self, "Copied!"); });
        } else {
          flash(self, pageUrl);
        }
        return;
      }
      if (target) window.open(target, "_blank", "noopener,noreferrer");
    });
  }
  function flash(el, msg) {
    var old = el.textContent;
    el.textContent = msg;
    setTimeout(function () { el.textContent = old; }, 1600);
  }

  /* ---- Form guard: stop submission while endpoint is a placeholder ----
     Prevents a broken POST to the literal string "[FORM ENDPOINT]". */
  var forms = document.querySelectorAll("form[data-form]");
  for (var f = 0; f < forms.length; f++) {
    forms[f].addEventListener("submit", function (e) {
      var action = this.getAttribute("action") || "";
      if (action.indexOf("[") !== -1 || action.trim() === "") {
        e.preventDefault();
        var note = this.querySelector("[data-form-note]");
        if (note) {
          note.hidden = false;
          note.textContent =
            "This form isn't connected yet. Add a form endpoint (Formspree / Netlify / Basin) in the action attribute to go live.";
        }
      }
    });
  }
})();
