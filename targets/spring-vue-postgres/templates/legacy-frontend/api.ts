import { accessToken } from './extensions/identity';

export async function call<T>(path: string, body?: unknown): Promise<T> {
  const token = await accessToken();
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) throw new Error(response.status === 403 ? 'Permission denied.' : response.status === 409 ? 'This task changed. Reload before trying again.' : 'The task could not be completed.');
  return response.json() as Promise<T>;
}
