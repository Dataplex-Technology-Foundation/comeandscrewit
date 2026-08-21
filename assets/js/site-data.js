/* =========================================================================
   site-data.js — loads volatile outbreak figures from an external JSON
   file (assets/data/outbreak-data.json) at page load and injects them
   into the DOM. Edit the JSON file ONCE and every page updates
   automatically — no need to touch this script.

   If a data-outbreak key is missing from the JSON (e.g. a figure with no
   verified source), the containing .stat-card is removed from the DOM
   rather than showing an empty or broken tile.
   ========================================================================= */

var OUTBREAK_DATA_URL = "assets/data/outbreak-data.json";

/* Populated once the external JSON has loaded. Kept as a global for any
   other script/console debugging that previously relied on OUTBREAK. */
var OUTBREAK = {};

/* Inject values into the DOM by data-attribute.
   Usage in HTML:  <span data-outbreak="usCases"></span>
   For arrays, values are joined with ", ".  */
(function injectOutbreakData() {
  function paint(data) {
    OUTBREAK = data;
    var nodes = document.querySelectorAll("[data-outbreak]");
    for (var i = 0; i < nodes.length; i++) {
      var key = nodes[i].getAttribute("data-outbreak");
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        var val = data[key];
        nodes[i].textContent = Array.isArray(val) ? val.join(", ") : val;
      } else {
        var card = nodes[i].closest(".stat-card");
        if (card) {
          card.parentNode.removeChild(card);
        }
        // otherwise leave the node's existing static content untouched
      }
    }
    // Also stamp any <time data-lastmod> elements for JSON-LD parity.
    var stamps = document.querySelectorAll("[data-lastupdated]");
    for (var j = 0; j < stamps.length; j++) {
      stamps[j].textContent = data.lastUpdated;
    }
  }

  function loadAndPaint() {
    fetch(OUTBREAK_DATA_URL, { cache: "no-cache" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Failed to load " + OUTBREAK_DATA_URL + ": " + response.status);
        }
        return response.json();
      })
      .then(paint)
      .catch(function (err) {
        // eslint-disable-next-line no-console
        console.error("site-data.js: could not load outbreak data", err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadAndPaint);
  } else {
    loadAndPaint();
  }
})();
