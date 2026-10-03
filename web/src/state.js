export function createStore(initial) {
  const original = structuredClone(initial);
  let state = structuredClone(initial);
  const listeners = new Set();
  const notify = () => listeners.forEach((fn) => fn(structuredClone(state)));
  return {
    getState: () => structuredClone(state),
    setState(patch) {
      state = { ...state, ...structuredClone(patch) };
      notify();
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    reset() {
      state = structuredClone(original);
      notify();
    },
  };
}
