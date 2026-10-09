/** Replace with the deployment's OIDC client boundary. No generated credentials. */
export async function accessToken(): Promise<string> {
  throw new Error('OIDC_CLIENT_NOT_CONFIGURED');
}

export function permissions(): ReadonlySet<string> {
  return new Set();
}
