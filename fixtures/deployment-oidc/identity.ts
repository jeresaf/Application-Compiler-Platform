/** Deployment-owned OAuth 2.0 authorization-code + PKCE adapter example.
 * Claims are presentation hints. Only the resource server authorizes requests.
 * No credentials, issuer, tenant, actor or permission policy is generated here.
 */
export type IdentityHints={actor:string;subject:string;tenant:string;permissions:ReadonlySet<string>};
type Config={issuer:string;clientId:string;redirectUri:string;scopes:readonly string[];
  hints:(claims:Readonly<Record<string,unknown>>)=>IdentityHints;developmentLoopback?:boolean};
let config:Config|undefined,token='',expiry=0;
let hints:IdentityHints={actor:'',subject:'',tenant:'',permissions:new Set()};
const listeners=new Set<()=>void>();
const key='acp-oidc-pending';
function changed(){listeners.forEach(f=>f());}
export function configure(value:Config){
 const issuer=new URL(value.issuer),redirect=new URL(value.redirectUri);
 if(issuer.protocol!=='https:' && !(value.developmentLoopback&&issuer.protocol==='http:'&&['127.0.0.1','localhost'].includes(issuer.hostname)))throw new Error('OIDC_HTTPS_REQUIRED');
 if(redirect.origin!==location.origin)throw new Error('OIDC_REDIRECT_ORIGIN');
 clearIdentity();config=value;
}
function configured(){if(!config)throw new Error('OIDC_CLIENT_NOT_CONFIGURED');return config;}
function base64url(bytes:Uint8Array){return btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');}
function random(){return base64url(crypto.getRandomValues(new Uint8Array(32)));}
async function discovery(){
 const cfg=configured();const response=await fetch(cfg.issuer.replace(/\/$/,'')+'/.well-known/openid-configuration');
 if(!response.ok)throw new Error('OIDC_DISCOVERY');const metadata=await response.json();
 if(metadata.issuer!==cfg.issuer)throw new Error('OIDC_ISSUER_MISMATCH');
 for(const key of ['authorization_endpoint','token_endpoint'])if(new URL(metadata[key]).origin!==new URL(cfg.issuer).origin)throw new Error('OIDC_ENDPOINT_ORIGIN');
 return metadata as {authorization_endpoint:string;token_endpoint:string};
}
export async function login(){
 const cfg=configured(),metadata=await discovery(),state=random(),nonce=random(),verifier=random();
 const challenge=base64url(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
 sessionStorage.setItem(key,JSON.stringify({state,nonce,verifier,created:Date.now()}));
 const url=new URL(metadata.authorization_endpoint);
 Object.entries({response_type:'code',client_id:cfg.clientId,redirect_uri:cfg.redirectUri,scope:cfg.scopes.join(' '),state,nonce,code_challenge:challenge,code_challenge_method:'S256'}).forEach(([k,v])=>url.searchParams.set(k,v));
 location.assign(url);
}
export async function callback(){
 const query=new URL(location.href).searchParams;if(!query.has('code')&&!query.has('error'))return false;
 const pending=sessionStorage.getItem(key);sessionStorage.removeItem(key);
 history.replaceState(null,'',configured().redirectUri);
 if(!pending)throw new Error('OIDC_STATE');const attempt=JSON.parse(pending);
 if(query.get('error')||query.get('state')!==attempt.state||Date.now()-attempt.created>300000)throw new Error('OIDC_STATE');
 const metadata=await discovery(),cfg=configured();
 const response=await fetch(metadata.token_endpoint,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:cfg.clientId,redirect_uri:cfg.redirectUri,code:query.get('code')!,code_verifier:attempt.verifier})});
 if(!response.ok){clearIdentity();throw new Error('OIDC_TOKEN_ACQUISITION');}
 const value=await response.json();
 if(value.token_type?.toLowerCase()!=='bearer'||typeof value.access_token!=='string'||!Number.isFinite(value.expires_in)||value.expires_in<=0)throw new Error('OIDC_TOKEN_RESPONSE');
 // ID-token claims are untrusted UI hints, never identity/authorization proof.
 // This example requires an ID token for nonce and deployment hint extraction;
 // server-side bearer validation remains mandatory independently of hints.
 const payload=value.id_token?.split('.')[1];if(!payload)throw new Error('OIDC_ID_TOKEN_REQUIRED');
 const claims=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(payload.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0))));
 if(claims.iss!==cfg.issuer||claims.aud!==cfg.clientId||claims.nonce!==attempt.nonce)throw new Error('OIDC_ID_TOKEN_BINDING');
 token=value.access_token;expiry=Date.now()+value.expires_in*1000;hints=cfg.hints(claims);changed();return true;
}
export function clearIdentity(){token='';expiry=0;hints={actor:'',subject:'',tenant:'',permissions:new Set()};changed();}
export function identity(){return hints;}
export function permissions(){return hints.permissions;}
export function onIdentityChange(listener:()=>void){listeners.add(listener);return ()=>{listeners.delete(listener);};}
export async function accessToken(){if(!token||Date.now()>=expiry){clearIdentity();throw new Error('OIDC_REAUTHENTICATION_REQUIRED');}return token;}
