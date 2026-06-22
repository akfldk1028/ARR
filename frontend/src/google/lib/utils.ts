export async function audioContext(_options?: { id?: string }): Promise<AudioContext> {
  const AudioContextCtor = window.AudioContext || (window as any).webkitAudioContext;
  return new AudioContextCtor();
}
