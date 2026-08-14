/* =========================================================================
   site-data.js — SINGLE SOURCE OF TRUTH for volatile outbreak figures.
   Edit these values ONCE and every page updates automatically.

   All figures are [VERIFY] — confirm against USDA-APHIS, CDC, and the Texas
   Animal Health Commission (TAHC) on the publish date before going live.
   Numbers below reflect early-July 2026 reporting and WILL be stale.
   ========================================================================= */

const OUTBREAK = {
  // Bump this on every update — it also drives the JSON-LD dateModified.
  lastUpdated: "[DATE]",            // e.g. "August 11, 2026"

  usCases: "[VERIFY:32]",           // confirmed U.S. animal cases
  usStates: ["Texas", "New Mexico"],
  usStateCount: "[VERIFY:2]",

  regionAnimalCases: "[VERIFY:185,000]",  // Mexico & Central America
  regionHumanCases: "[VERIFY:2,263]",     // regional human myiasis cases

  firstUsCase: "[VERIFY: Zavala County, Texas — June 3, 2026]",

  // Affected counties — surfaced on status/rancher pages for local SEO.
  affectedCounties: ["Zavala", "Maverick", "La Salle"], // [VERIFY current counties]

  sterilePupaePerWeek: "[VERIFY:100M+]"   // COPEG facility, Pacora, Panama
};

/* Inject values into the DOM by data-attribute.
   Usage in HTML:  <span data-outbreak="usCases"></span>
   For arrays, values are joined with ", ".  */
(function injectOutbreakData() {
  function paint() {
    var nodes = document.querySelectorAll("[data-outbreak]");
    for (var i = 0; i < nodes.length; i++) {
      var key = nodes[i].getAttribute("data-outbreak");
      if (Object.prototype.hasOwnProperty.call(OUTBREAK, key)) {
        var val = OUTBREAK[key];
        nodes[i].textContent = Array.isArray(val) ? val.join(", ") : val;
      }
    }
    // Also stamp any <time data-lastmod> elements for JSON-LD parity.
    var stamps = document.querySelectorAll("[data-lastupdated]");
    for (var j = 0; j < stamps.length; j++) {
      stamps[j].textContent = OUTBREAK.lastUpdated;
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", paint);
  } else {
    paint();
  }
})();
