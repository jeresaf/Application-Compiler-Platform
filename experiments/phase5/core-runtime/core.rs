use std::collections::HashSet;
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::time::Instant;
#[derive(Clone,Debug,Eq,PartialEq,Hash)]
struct Subject { id:usize, revision:u32 }
#[derive(Debug)]
struct Diagnostic { code:&'static str, subject:Subject, locator:String }
trait GraphPort { fn successors(&self, subject:&Subject)->Vec<Subject>; }
struct Chain { count:usize }
impl GraphPort for Chain {fn successors(&self,s:&Subject)->Vec<Subject>{if s.id+1<self.count {vec![Subject{id:s.id+1,revision:1}]}else{vec![]}}}
fn traverse(root:Subject,port:&dyn GraphPort,budget:usize,cancelled:&AtomicBool)->Result<Vec<Subject>,Diagnostic>{
 let mut pending=vec![root];let mut seen=HashSet::new();let mut visited=Vec::new();let mut cursor=0;
 while cursor<pending.len(){let next=pending[cursor].clone();cursor+=1;
  let fail=|code| Diagnostic{code,subject:next.clone(),locator:format!("corpus/graph#{}",next.id)};
  if cancelled.load(Ordering::Relaxed){return Err(fail("CANCELLED"));}
  if seen.contains(&next){continue;}
  if seen.len()>=budget{return Err(fail("WORK_LIMIT"));}
  seen.insert(next.clone());visited.push(next.clone());pending.extend(port.successors(&next));
 }Ok(visited)
}
fn main(){let count=std::env::args().nth(1).unwrap().parse::<usize>().unwrap();let port=Chain{count};let root=Subject{id:0,revision:1};let mut timings=Vec::new();
 for _ in 0..8 {let start=Instant::now();assert_eq!(traverse(root.clone(),&port,count,&AtomicBool::new(false)).unwrap().len(),count);timings.push(start.elapsed().as_secs_f64()*1000.0);}
 let d=traverse(root.clone(),&port,0,&AtomicBool::new(false)).unwrap_err();assert_eq!(d.code,"WORK_LIMIT");assert_eq!(d.subject,root);assert!(d.locator.starts_with("corpus/"));
 assert_eq!(traverse(root.clone(),&port,count,&AtomicBool::new(true)).unwrap_err().code,"CANCELLED");
 let shared=Arc::new(port);let handles:Vec<_>=(0..8).map(|_|{let port=shared.clone();std::thread::spawn(move||traverse(Subject{id:0,revision:1},port.as_ref(),count,&AtomicBool::new(false)).unwrap().len())}).collect();for handle in handles{assert_eq!(handle.join().unwrap(),count);}
 println!("{{\"candidate\":\"Rust 1.90.0\",\"nodes\":{},\"graphMs\":{:?},\"cancellation\":true,\"workLimit\":true,\"concurrentRuns\":8,\"canonical\":\"NOT_RUN\"}}",count,timings);
}
