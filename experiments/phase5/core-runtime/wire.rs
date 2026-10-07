#[allow(dead_code)] mod strict {include!("canonical.rs");}
use serde_json::{Value,json};
use std::{io::{self,BufRead},collections::{BTreeMap,VecDeque},time::Instant};
#[derive(Clone)] struct Request {id:String,protocol:String,canonical:String,provenance:Vec<Value>,obligations:Vec<Value>,dependencies:BTreeMap<String,Vec<String>>,budget:usize,cancelled:bool,port_version:String}
impl Request {fn parse(v:&Value)->Self{Self{id:v["id"].as_str().unwrap().into(),protocol:v["protocol"].as_str().unwrap().into(),canonical:v["canonicalInput"].as_str().unwrap().into(),provenance:v["provenance"].as_array().unwrap().clone(),obligations:v["obligations"].as_array().unwrap().clone(),dependencies:v["dependencies"].as_object().unwrap().iter().map(|(k,v)|(k.clone(),v.as_array().unwrap().iter().map(|s|s.as_str().unwrap().into()).collect())).collect(),budget:v["budget"].as_u64().unwrap() as usize,cancelled:v["cancelled"].as_bool().unwrap(),port_version:v["portVersion"].as_str().unwrap().into()}}}
enum Result {Success(Vec<String>),Failure(&'static str)}
trait Port {fn successors(&self,id:&str)->Vec<String>;}
impl Port for Request {fn successors(&self,id:&str)->Vec<String>{self.dependencies.get(id).cloned().unwrap_or_default()}}
fn traverse(r:&Request)->Result {let mut visited=Vec::new();let mut pending=VecDeque::from([String::from("ROOT")]);let mut code="";
 if r.protocol!="acp-core-wire/1"{code="VERSION";}else if r.port_version!="graph/1"{code="PORT";}else if strict::encode(&strict::parse(r.canonical.as_bytes()).unwrap())!=r.canonical{code="CANONICAL";}
 while code.is_empty()&&!pending.is_empty(){let id=pending.pop_front().unwrap();if r.cancelled{code="CANCELLED";break;}if visited.contains(&id){continue;}if visited.len()>=r.budget{code="RESOURCE";break;}visited.push(id.clone());pending.extend(r.successors(&id));}
 if code.is_empty(){Result::Success(visited)}else{Result::Failure(code)}
}
fn execute(r:&Request)->Value {let (code,visited)=match traverse(r){Result::Success(v)=>("",v),Result::Failure(c)=>(c,vec![])};
 if !code.is_empty(){return json!({"protocol":"acp-core-wire/1","id":r.id,"status":"FAILURE","diagnostics":[{"code":code,"subject":"ROOT","primary":"graph.acp#L1C1","related":[],"remediation":"Repair the declared request or retry with valid authority and budgets."}]});}
 json!({"protocol":"acp-core-wire/1","id":r.id,"status":if code.is_empty(){"SUCCESS"}else{"FAILURE"},"diagnostics":if code.is_empty(){json!([])}else{json!([{"code":code,"subject":"ROOT","primary":"graph.acp#L1C1","related":[],"remediation":"Repair the declared request or retry with valid authority and budgets."}])},"digest":strict::hash(&strict::parse(r.canonical.as_bytes()).unwrap(),"canonical"),"provenance":r.provenance,"obligations":r.obligations,"work":visited.len(),"visited":visited})
}
fn main(){for line in io::stdin().lock().lines(){let line=line.unwrap();let start=Instant::now();let value=strict::parse(line.as_bytes()).unwrap();let r=Request::parse(&value);let decoded=start.elapsed();let out=strict::encode(&execute(&r));println!("{}",out);if std::env::var_os("ACP_WIRE_METRICS").is_some(){eprintln!("{}",json!({"decodeNs":decoded.as_nanos() as u64,"executeEncodeNs":start.elapsed().as_nanos() as u64-decoded.as_nanos() as u64,"inputBytes":line.len(),"outputBytes":out.len()}));}}}
