// Macintosh System 6 window manager
// Handles: drag, click-to-focus, fold/unfold

export class WindowManager {
  constructor() {
    this.highestZ = 100;
    this.init();
  }

  init() {
    document.querySelectorAll(".window").forEach((win) => {
      this.setupDrag(win);
      this.setupFocus(win);
    });
  }

  setupDrag(win) {
    const titleBar = win.querySelector(".title-bar");
    if (!titleBar) return;

    let offsetX = 0;
    let offsetY = 0;
    let dragging = false;

    titleBar.addEventListener("mousedown", (e) => {
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

    // Double-click to fold
    titleBar.addEventListener("dblclick", () => {
      const content = win.querySelector(".window-content");
      if (content) {
        content.style.display =
          content.style.display === "none" ? "block" : "none";
      }
    });
  }

  setupFocus(win) {
    win.addEventListener("mousedown", () => {
      this.focus(win);
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
