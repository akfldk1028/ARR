/**
 * CF Pages Function — proxy /law/*, /land/*, /design/* to Railway ARR backend.
 * Catches all requests, only proxies known API prefixes, else passes through to static.
 */
const BACKEND = 'https://arr-backend-production.up.railway.app';
const API_PREFIXES = ['/law/', '/land/', '/design/'];

export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  const isApi = API_PREFIXES.some((p) => url.pathname.startsWith(p));

  if (!isApi) {
    return context.next();
  }

  const target = `${BACKEND}${url.pathname}${url.search}`;
  const headers = new Headers(context.request.headers);
  headers.set('Host', new URL(BACKEND).host);

  const resp = await fetch(target, {
    method: context.request.method,
    headers,
    body: context.request.method !== 'GET' ? context.request.body : undefined,
  });

  const respHeaders = new Headers(resp.headers);
  respHeaders.set('Access-Control-Allow-Origin', '*');

  return new Response(resp.body, {
    status: resp.status,
    headers: respHeaders,
  });
};
