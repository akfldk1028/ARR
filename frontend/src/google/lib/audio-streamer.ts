export class AudioStreamer {
  gainNode: GainNode;
  constructor(private audioContext: AudioContext) {
    this.gainNode = audioContext.createGain();
  }
  async addWorklet<T>(_name: string, _worklet: unknown, _callback: (event: T) => void) {}
  addPCM16(_data: Uint8Array) {}
  stop() {}
}
