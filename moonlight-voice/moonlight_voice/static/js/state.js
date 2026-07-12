export function createState(initial = {}) {
  const values = { ...initial };
  const events = new EventTarget();

  return {
    get(key) {
      return values[key];
    },
    set(key, value) {
      values[key] = value;
      events.dispatchEvent(
        new CustomEvent("change", { detail: { key, value } }),
      );
    },
    subscribe(listener) {
      events.addEventListener("change", listener);
      return () => events.removeEventListener("change", listener);
    },
  };
}
