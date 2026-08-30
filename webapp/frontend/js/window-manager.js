// Macintosh System 6 window manager
// Handles: drag, click-to-focus, fold/unfold, close button

export class WindowManager {
  constructor() {
    this.highestZ = 100;
    this.init();
  }

  init() {
    document.querySelectorAll(".window").forEach((win) => {
      this.setupDrag(win);
      this.setupFocus(win);
      this.setupFold(win);
    });
  }

  setupDrag(win) {
    const titleBar = win.querySelector(".title-bar");
    if (!titleBar) return;

    let offsetX = 0;
    let offsetY = 0;
    let dragging = false;

    titleBar.addEventListener("mousedown", (e) => {
      if (e.target.closest("button")) return;
      dragging = true;
      offsetX = e.clientX - win.offsetLeft;
      offsetY = e.clientY - win.offsetTop;
      this.focus(win);
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      win.style.left = `${e.clientX - offsetX}px`;
      win.style.top = `${e.clientY - offsetY}px`;
    });

    document.addEventListener("mouseup", () => {
      dragging = false;
    });
  }

  setupFocus(win) {
    win.addEventListener("mousedown", () => {
      this.focus(win);
    });
  }

  setupFold(win) {
    const titleBar = win.querySelector(".title-bar");
    if (!titleBar) return;

    titleBar.addEventListener("dblclick", (e) => {
      if (e.target.closest("button")) return;
      const pane = win.querySelector(".window-pane");
      const separator = win.querySelector(".separator");
      const hidden = pane && pane.style.display === "none";
      if (pane) pane.style.display = hidden ? "block" : "none";
      if (separator) separator.style.display = hidden ? "flex" : "none";
    });
  }

  focus(win) {
    document.querySelectorAll(".window").forEach((w) =>
      w.classList.remove("focused")
    );
    this.highestZ++;
    win.style.zIndex = this.highestZ;
    win.classList.add("focused");
  }
}
