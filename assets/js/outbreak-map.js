/* outbreak-map.js — renders the confirmed-county map on outbreak-status.html
   using Leaflet + OpenStreetMap tiles (no API key required). Marker
   coordinates are approximate county-seat locations, not exact case sites —
   see the map caption for that disclosure. Reads the same
   assets/data/outbreak-data.json that site-data.js paints text from. */

(function () {
  function renderMap(data) {
    var el = document.getElementById("outbreak-map");
    if (!el || typeof L === "undefined") return;

    var counties = data.affectedCounties || [];
    var coords = data.countyCoordinates || {};
    var markers = [];

    var map = L.map(el, { scrollWheelZoom: false }).setView([29.5, -100.5], 6);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    for (var i = 0; i < counties.length; i++) {
      var name = counties[i];
      var point = coords[name];
      if (!point) continue;
      var marker = L.marker([point.lat, point.lon]).addTo(map);
      marker.bindPopup("<strong>" + name + " County, " + point.state + "</strong>");
      markers.push(marker);
    }

    if (markers.length) {
      var group = L.featureGroup(markers);
      map.fitBounds(group.getBounds().pad(0.2));
    }
  }

  function init() {
    var el = document.getElementById("outbreak-map");
    if (!el) return;
    fetch("assets/data/outbreak-data.json", { cache: "no-cache" })
      .then(function (response) {
        if (!response.ok) throw new Error("Failed to load outbreak data: " + response.status);
        return response.json();
      })
      .then(renderMap)
      .catch(function (err) {
        console.error("outbreak-map.js: could not render map", err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
