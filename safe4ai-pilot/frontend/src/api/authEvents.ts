type UnauthorizedHandler = () => void;

const handlers = new Set<UnauthorizedHandler>();

export function onUnauthorized(handler: UnauthorizedHandler) {
  handlers.add(handler);
  return () => {
    handlers.delete(handler);
  };
}

export function emitUnauthorized() {
  for (const handler of handlers) {
    handler();
  }
}
