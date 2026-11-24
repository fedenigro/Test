// Site interactions: scroll reveal, reading progress, full-screen images.
// Every effect is optional — the page works fully without this file.
(function () {
  "use strict";
  window.__motion = true;
  var root = document.documentElement;
  var motion = root.classList.contains("js-motion");

  /* ---------- 1. Fade-in on scroll ---------- */
  // Keep this list in sync with the .js-motion rules in css/style.css.
  var REVEAL = ".intro > *, .section-label, .work-list li, .tags, .about > *, .case-head > *, " +
    ".meta-grid > div, .narrow > *, .case > figure, .grid > figure, .embed, .callout";

  if (motion) {
    var io = new IntersectionObserver(function (entries) {
      var batch = 0;
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.style.transitionDelay = Math.min(batch++, 5) * 70 + "ms";
        e.target.classList.add("in");
        io.unobserve(e.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    document.querySelectorAll(REVEAL).forEach(function (el) { io.observe(el); });
  }

  /* ---------- 2. Reading progress (case studies) ---------- */
  if (document.querySelector(".case")) {
    var bar = document.createElement("div");
    bar.className = "progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.appendChild(bar);
    var ticking = false;
    var update = function () {
      var max = root.scrollHeight - root.clientHeight;
      bar.style.transform = "scaleX(" + (max > 0 ? Math.min(1, root.scrollTop / max) : 0) + ")";
      ticking = false;
    };
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  /* ---------- 3. Full-screen images (case studies) ---------- */
  var imgs = Array.prototype.slice.call(document.querySelectorAll(".case figure img"));
  if (imgs.length && window.HTMLDialogElement) {
    var dlg = document.createElement("dialog");
    dlg.className = "lightbox";
    dlg.setAttribute("aria-label", "Image viewer");
    dlg.innerHTML =
      '<img alt="">' +
      '<button type="button" class="lb-close" aria-label="Close">×</button>' +
      '<button type="button" class="lb-prev" aria-label="Previous image">‹</button>' +
      '<button type="button" class="lb-next" aria-label="Next image">›</button>' +
      '<p class="lb-count"></p>';
    document.body.appendChild(dlg);
    var big = dlg.querySelector("img");
    var count = dlg.querySelector(".lb-count");
    var current = 0;

    var show = function (i) {
      current = (i + imgs.length) % imgs.length;
      var src = imgs[current];
      var link = src.closest("a");
      big.src = link ? link.href : (src.currentSrc || src.src);
      big.alt = src.alt;
      count.textContent = (current + 1) + " / " + imgs.length;
    };

    imgs.forEach(function (img, i) {
      var target = img.closest("a") || img;
      target.classList.add("zoomable");
      if (target === img) { img.tabIndex = 0; img.setAttribute("role", "button"); }
      var open = function (ev) { ev.preventDefault(); show(i); dlg.showModal(); };
      target.addEventListener("click", open);
      if (target === img) target.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") open(ev);
      });
    });

    dlg.querySelector(".lb-close").addEventListener("click", function () { dlg.close(); });
    dlg.querySelector(".lb-prev").addEventListener("click", function () { show(current - 1); });
    dlg.querySelector(".lb-next").addEventListener("click", function () { show(current + 1); });
    big.addEventListener("click", function () { dlg.close(); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) dlg.close(); });
    dlg.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowLeft") show(current - 1);
      if (ev.key === "ArrowRight") show(current + 1);
    });
    if (imgs.length < 2) { dlg.querySelector(".lb-prev").hidden = true; dlg.querySelector(".lb-next").hidden = true; }
  }
})();
