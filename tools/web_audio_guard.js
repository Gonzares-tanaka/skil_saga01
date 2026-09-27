// Loaded before Pyxel's Web runtime. Audio failures never affect game input.
(() => {
  const contexts = new Set();
  const wrappers = new Map();
  const events = [];
  for (const name of ["AudioContext", "webkitAudioContext"]) {
    const Native = window[name];
    if (typeof Native !== "function") continue;
    if (!wrappers.has(Native)) {
      wrappers.set(Native, new Proxy(Native, {
        construct(target, args, newTarget) {
          const context = Reflect.construct(target, args, newTarget);
          contexts.add(context);
          return context;
        }
      }));
    }
    try { window[name] = wrappers.get(Native); } catch (_) { /* read-only browser alias */ }
  }

  function audioContext() {
    const sdl = window.SDL2?.audioContext || window.Module?.SDL2?.audioContext;
    if (sdl) return sdl;
    return [...contexts].reverse().find(context => context.state !== "closed") ||
           [...contexts].reverse()[0] || null;
  }

  window.sparkAudioState = () => audioContext()?.state || "unavailable";
  window.sparkAudioEvents = events;
  window.sparkResumeAudio = () => {
    const context = audioContext();
    if (!context || context.state === "running" || context.state === "closed") return;
    try {
      Promise.resolve(context.resume()).then(
        () => record("resume"),
        error => record("resume-failed:" + String(error))
      );
    } catch (error) {
      record("resume-failed:" + String(error));
    }
  };

  function releaseButtons() {
    if (typeof _virtualGamepadStates !== "undefined") {
      _virtualGamepadStates.fill(false);
    }
  }

  function record(event) {
    const line = event + " hidden=" + document.hidden + " audio=" + window.sparkAudioState();
    events.push(line);
    if (events.length > 40) events.shift();
    console.info("[SPARK] " + line);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) releaseButtons();
    record("visibilitychange");
  });
  window.addEventListener("pagehide", () => { releaseButtons(); record("pagehide"); });
  window.addEventListener("pageshow", () => record("pageshow"));
  window.addEventListener("blur", () => { releaseButtons(); record("blur"); });
  window.addEventListener("focus", () => record("focus"));
  document.addEventListener("pointerdown", window.sparkResumeAudio, { capture: true });
  document.addEventListener("keydown", window.sparkResumeAudio, { capture: true });
})();
