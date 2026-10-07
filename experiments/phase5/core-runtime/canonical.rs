use serde_json::{Value,Map,Number};
use sha2::{Sha256,Digest};
use std::{fs,path::Path};
struct Parser<'a>{raw:&'a [u8],i:usize}
impl Parser<'_>{
 fn skip(&mut self){while self.i<self.raw.len()&&b" \t\r\n".contains(&self.raw[self.i]){self.i+=1;}}
 fn string(&mut self)->Result<String,String>{let start=self.i;if self.raw.get(self.i)!=Some(&b'"'){return Err("string".into());}self.i+=1;
  while self.i<self.raw.len(){match self.raw[self.i]{b'\\'=>{self.i+=2;},b'"'=>{self.i+=1;return serde_json::from_slice(&self.raw[start..self.i]).map_err(|e|e.to_string());},_=>self.i+=1,}}
  Err("unterminated".into())
 }
 fn value(&mut self,depth:usize)->Result<Value,String>{if depth>48{return Err("depth".into());}self.skip();match self.raw.get(self.i).copied(){
  Some(b'"')=>Ok(Value::String(self.string()?)),
  Some(b'{'|b'[')=>{let object=self.raw[self.i]==b'{';let end=if object{b'}'}else{b']'};self.i+=1;self.skip();let mut map=Map::new();let mut array=vec![];
   if self.raw.get(self.i)==Some(&end){self.i+=1;return Ok(if object{Value::Object(map)}else{Value::Array(array)});}
   loop {self.skip();if object{let key=self.string()?;if map.contains_key(&key){return Err("duplicate".into());}self.skip();if self.raw.get(self.i)!=Some(&b':'){return Err("colon".into());}self.i+=1;map.insert(key,self.value(depth+1)?);}else{array.push(self.value(depth+1)?);}self.skip();if self.raw.get(self.i)==Some(&end){self.i+=1;break;}if self.raw.get(self.i)!=Some(&b','){return Err("comma".into());}self.i+=1;}
   Ok(if object{Value::Object(map)}else{Value::Array(array)})},
  Some(b'n')=>{self.word(b"null")?;Ok(Value::Null)},Some(b't')=>{self.word(b"true")?;Ok(Value::Bool(true))},Some(b'f')=>{self.word(b"false")?;Ok(Value::Bool(false))},
  Some(b'-'|b'0'..=b'9')=>{let start=self.i;if self.raw[self.i]==b'-'{self.i+=1;}let digits=self.i;while self.raw.get(self.i).is_some_and(u8::is_ascii_digit){self.i+=1;}if digits==self.i||self.i-digits>1&&self.raw[digits]==b'0'{return Err("integer".into());}let n=std::str::from_utf8(&self.raw[start..self.i]).unwrap().parse::<i64>().map_err(|e|e.to_string())?;if !(-9007199254740991..=9007199254740991).contains(&n){return Err("unsafe".into());}Ok(Value::Number(Number::from(n)))},
  _=>Err("token".into())
 }}
 fn word(&mut self,w:&[u8])->Result<(),String>{if self.raw.get(self.i..self.i+w.len())!=Some(w){return Err("token".into());}self.i+=w.len();Ok(())}
}
fn parse(raw:&[u8])->Result<Value,String>{if raw.len()>1048576||raw.starts_with(&[239,187,191]){return Err("size/bom".into());}std::str::from_utf8(raw).map_err(|e|e.to_string())?;let mut p=Parser{raw,i:0};let v=p.value(0)?;p.skip();if p.i!=raw.len(){return Err("trailing".into());}Ok(v)}
fn encode(v:&Value)->String{match v{Value::Object(m)=>{let mut keys:Vec<_>=m.keys().collect();keys.sort_by(|a,b|a.encode_utf16().cmp(b.encode_utf16()));format!("{{{}}}",keys.iter().map(|k|format!("{}:{}",serde_json::to_string(k).unwrap(),encode(&m[*k]))).collect::<Vec<_>>().join(","))},Value::Array(a)=>format!("[{}]",a.iter().map(encode).collect::<Vec<_>>().join(",")),_=>serde_json::to_string(v).unwrap()}}
fn hash(v:&Value,domain:&str)->String{let mut h=Sha256::new();h.update(format!("ACP\0acp-jcs-safe-v1\0{domain}\0").as_bytes());h.update(encode(v).as_bytes());format!("sha256:{:x}",h.finalize())}
fn main(){let root=std::env::args().nth(1).unwrap();let root=Path::new(&root);let vectors=parse(&fs::read(root.join("byte-vectors.json")).unwrap()).unwrap();
 for v in vectors["positive"].as_array().unwrap(){let value=parse(v["input"].as_str().unwrap().as_bytes()).unwrap();assert_eq!(encode(&value),v["canonical"].as_str().unwrap(),"{}",v["name"]);assert_eq!(hash(&value,"vector"),v["digest"].as_str().unwrap());}
 for v in vectors["negative"].as_array().unwrap(){assert!(parse(v["input"].as_str().unwrap().as_bytes()).is_err(),"{}",v["name"]);}
 assert!(parse(&[255]).is_err());assert!(parse(&vec![32;1048577]).is_err());
 let manifest=parse(&fs::read(root.join("manifest.json")).unwrap()).unwrap();for v in manifest["examples"].as_array().unwrap(){let snapshot=parse(&fs::read(root.join(v["file"].as_str().unwrap())).unwrap()).unwrap();assert_eq!(hash(&snapshot["content"],"canonical"),v["contentDigest"].as_str().unwrap());}
 println!("{{\"candidate\":\"Rust 1.90.0 / serde_json 1.0.145 / sha2 0.10.9\",\"positive\":{},\"negative\":{},\"snapshotHashes\":{},\"status\":\"PASS\"}}",vectors["positive"].as_array().unwrap().len(),vectors["negative"].as_array().unwrap().len(),manifest["examples"].as_array().unwrap().len());
}
