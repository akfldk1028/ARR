import { EventEmitter } from 'eventemitter3';
import type { LiveConnectConfig } from '@google/genai';

export class GenAILiveClient extends EventEmitter {
  constructor(private apiKey: string, private model: string) {
    super();
  }
  async connect(_config: LiveConnectConfig) {
    this.emit('open');
    this.emit('setupcomplete');
  }
  disconnect() {
    this.emit('close', new CloseEvent('close'));
  }
  sendRealtimeInput(_input: Array<unknown>) {}
  sendRealtimeText(_text: string) {}
  sendToolResponse(_response: unknown) {}
}
