type Handler = (data: string) => void;

export class AudioRecorder {
  private handlers = new Set<Handler>();
  on(_event: 'data', handler: Handler) {
    this.handlers.add(handler);
  }
  off(_event: 'data', handler: Handler) {
    this.handlers.delete(handler);
  }
  start() {}
  stop() {}
}
