import { accessToken } from './extensions/identity';
export type SafeOutcome='UNAUTHENTICATED'|'DENIED'|'STALE'|'IN_PROGRESS'|'IDEMPOTENCY_CONFLICT'|'SEMANTIC_FAILURE'|'RATE_DENIED'|'INVALID'|'INTERNAL'|'NETWORK';
export const FAILURE_HTTP_PROFILE="1.0.0" as const;
export type SemanticFailureEnvelope={failureId:string;failureRevision:number;code:string;category:string;retryable:boolean;operationId:string;operationRevision:number;correlationId:string};
export class ApiFailure extends Error{constructor(public readonly outcome:SafeOutcome){super(outcome);}}
export async function call<T>(path:string,body?:unknown):Promise<T>{
 let token:string;try{token=await accessToken();}catch{throw new ApiFailure('UNAUTHENTICATED');}
 let response:Response;try{response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});}catch{throw new ApiFailure('NETWORK');}
 if(response.status===202)throw new ApiFailure('IN_PROGRESS');
 if(!response.ok){let code='';try{const data:unknown=await response.json();if(typeof data==='object' && data!==null && 'code' in data && typeof data.code==='string')code=data.code;}catch{/* no raw body surfaced */}
 const outcome:SafeOutcome=response.headers.get('ACP-Failure-Profile')===FAILURE_HTTP_PROFILE?'SEMANTIC_FAILURE':response.status===401?'UNAUTHENTICATED':response.status===403?'DENIED':response.status===429?'RATE_DENIED':response.status===422?'SEMANTIC_FAILURE':response.status===409?(code==='IN_PROGRESS'?'IN_PROGRESS':code==='IDEMPOTENCY_CONFLICT'?'IDEMPOTENCY_CONFLICT':'STALE'):response.status===400?'INVALID':'INTERNAL';throw new ApiFailure(outcome);}
 try{return await response.json() as T;}catch{throw new ApiFailure('NETWORK');}
}
