// Reads a document and prepares its elements for actions. It runs in an isolated world, so the
// page's own scripts cannot see it or change it. One entry point: __bap(operation, arguments).
(() => {
  if (globalThis.__bap) return;

  // Resolves at the next animation frame, or after `ms` on a page that is not being painted.
  const nextFrame = (ms) =>
    new Promise((done) => {
      const timer = setTimeout(done, ms);
      requestAnimationFrame(() => {
        clearTimeout(timer);
        done();
      });
    });

  async function frames(a) {
    for (let i = 0; i < a.count; i++) await nextFrame(a.frameMs);
    return true;
  }

  const operations = { frames };

  globalThis.__bap = (operation, a) => {
    const run = operations[operation];
    if (!run) throw new Error('unknown operation ' + operation);
    return run(a);
  };
})();
