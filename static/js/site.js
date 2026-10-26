(function () {
  const root = document.documentElement;

  function currentMode() {
    if (root.classList.contains("high-contrast")) return "contrast";
    if (root.classList.contains("light-mode")) return "light";
    return "dark";
  }

  function setMode(mode) {
    root.classList.remove("light-mode", "high-contrast");
    if (mode === "light") root.classList.add("light-mode");
    if (mode === "contrast") root.classList.add("high-contrast");
    try {
      localStorage.setItem("theme-mode", mode);
    } catch (err) {
      /* storage can be blocked */
    }
    const dark = document.getElementById("toggle-dark");
    const contrast = document.getElementById("toggle-contrast");
    if (dark) dark.setAttribute("aria-pressed", mode === "dark" ? "true" : "false");
    if (contrast) contrast.setAttribute("aria-pressed", mode === "contrast" ? "true" : "false");
  }

  document.getElementById("toggle-dark")?.addEventListener("click", () => {
    setMode(currentMode() === "dark" ? "light" : "dark");
  });
  document.getElementById("toggle-contrast")?.addEventListener("click", () => {
    setMode(currentMode() === "contrast" ? "dark" : "contrast");
  });
  setMode(currentMode());

  const nav = document.getElementById("nav");
  const navToggle = document.getElementById("nav-toggle");
  navToggle?.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.getElementById("nav-links")?.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      nav.classList.remove("is-open");
      navToggle?.setAttribute("aria-expanded", "false");
    }
  });

  const older = document.getElementById("older-posts");
  const olderBtn = document.getElementById("show-older");
  olderBtn?.addEventListener("click", () => {
    const willShow = older.hasAttribute("hidden");
    if (willShow) older.removeAttribute("hidden");
    else older.setAttribute("hidden", "");
    olderBtn.setAttribute("aria-expanded", willShow ? "true" : "false");
    const label = olderBtn.querySelector("span");
    if (label) label.textContent = willShow ? "Hide older notes" : "Show older notes";
  });

  const toTop = document.getElementById("to-top");
  if (toTop) {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.addEventListener(
      "scroll",
      () => {
        toTop.classList.toggle("is-visible", window.scrollY > 480);
      },
      { passive: true }
    );
    toTop.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    });
  }
})();
