export class OAuth {
  async startOAuth(provider: string): Promise<void> {
    console.warn(`[OAuth] startOAuth stub called for ${provider}`);
  }

  async handleCallback(provider: string, code: string): Promise<void> {
    console.warn(`[OAuth] handleCallback stub called for ${provider}`, code);
  }
}
