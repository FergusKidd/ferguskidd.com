(function () {
  try {
    var mode = localStorage.getItem("theme-mode");
    var root = document.documentElement;
    if (mode === "light") root.classList.add("light-mode");
    else if (mode === "contrast") root.classList.add("high-contrast");
    else if (!mode && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
      root.classList.add("light-mode");
    }
  } catch (err) {
    /* keep the dark default */
  }
})();
