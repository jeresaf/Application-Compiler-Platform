/** Deployment-owned OIDC integration. Hints affect presentation only; the server authorizes. */
export type IdentityHints={ actor:string; subject:string; tenant:string; permissions:ReadonlySet<string> };
export function identity():IdentityHints{return {actor:'',subject:'',tenant:'',permissions:new Set()};}
/** Notify on login/logout/tenant/session changes so protected UI state is discarded. */
export function onIdentityChange(_listener:()=>void):()=>void{return ()=>{};}
export async function accessToken():Promise<string>{throw new Error('OIDC_CLIENT_NOT_CONFIGURED');}
/** permissions() does not prove authorization. */
export function permissions():ReadonlySet<string>{return identity().permissions;}
