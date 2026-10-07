import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.*;
/** Bounded experimental fault slice. A Failure has no output or partial graph. */
public final class FaultCore {
 static final int LIMIT=1048576;
 static JsonObject failure(String id,String code){var o=new JsonObject();o.addProperty("protocol","acp-core-fault/1");o.addProperty("id",id);o.addProperty("status","FAILURE");var ds=new JsonArray();var d=new JsonObject();d.addProperty("code",code);d.addProperty("subject","ROOT");d.addProperty("primary","graph.acp#L1C1");d.add("related",new JsonArray());d.addProperty("remediation","Repair the declared request or retry with valid authority and budgets.");ds.add(d);o.add("diagnostics",ds);return o;}
 static JsonObject execute(byte[] raw){String id="unknown";String code="MALFORMED";
  try {if(raw.length>LIMIT)return failure(id,"INPUT_SIZE");var r=Canonical.parse(raw).getAsJsonObject();if(!Canonical.encode(r).equals(new String(raw,StandardCharsets.UTF_8)))return failure(id,code);if(r.has("id")&&r.get("id").isJsonPrimitive()&&r.getAsJsonPrimitive("id").isString())id=r.get("id").getAsString();
   if(!r.keySet().equals(Set.of("id","protocol","semanticVersion","canonicalInput","digest","dependencies","budget","cancelled","portVersion","downstream")))return failure(id,code);
   for(String k:List.of("id","protocol","semanticVersion","canonicalInput","digest","portVersion"))if(!r.get(k).isJsonPrimitive()||!r.getAsJsonPrimitive(k).isString())return failure(id,code);
   if(!r.get("cancelled").isJsonPrimitive()||!r.getAsJsonPrimitive("cancelled").isBoolean()||!r.get("budget").isJsonPrimitive()||!r.getAsJsonPrimitive("budget").isNumber()||r.get("budget").getAsLong()<0)return failure(id,code);
   var graph=r.getAsJsonObject("dependencies");for(var e:graph.entrySet())for(var v:e.getValue().getAsJsonArray())if(!v.isJsonPrimitive()||!v.getAsJsonPrimitive().isString())return failure(id,code);
   if(!r.get("protocol").getAsString().equals("acp-core-fault/1"))return failure(id,"VERSION");
   if(!r.get("semanticVersion").getAsString().equals("0.2.0"))return failure(id,"SEMANTIC_VERSION");
   if(!r.get("portVersion").getAsString().equals("graph/1"))return failure(id,"PORT_VERSION");
   JsonElement content;try{content=Canonical.parse(r.get("canonicalInput").getAsString().getBytes(StandardCharsets.UTF_8));}catch(Exception ignored){return failure(id,"CANONICAL");}if(!Canonical.encode(content).equals(r.get("canonicalInput").getAsString()))return failure(id,"CANONICAL");
   if(!Canonical.digest(content,"canonical").equals(r.get("digest").getAsString()))return failure(id,"DIGEST");
   if(!r.get("downstream").isJsonObject())return failure(id,"DOWNSTREAM");var down=r.getAsJsonObject("downstream");if(!down.keySet().equals(Set.of("protocol","status"))||!down.get("protocol").getAsString().equals("graph/1")||!down.get("status").getAsString().equals("SUCCESS"))return failure(id,"DOWNSTREAM");
   var visited=new ArrayList<String>();var pending=new ArrayDeque<String>();pending.add("ROOT");
   while(!pending.isEmpty()){String n=pending.remove();if(r.get("cancelled").getAsBoolean())return failure(id,"CANCELLED");if(visited.contains(n))continue;if(visited.size()>=r.get("budget").getAsLong())return failure(id,"RESOURCE");if(!graph.has(n))return failure(id,"DEPENDENCY");visited.add(n);for(var v:graph.getAsJsonArray(n))pending.add(v.getAsString());}
   var out=new JsonObject();out.addProperty("protocol","acp-core-fault/1");out.addProperty("id",id);out.addProperty("status","SUCCESS");out.add("diagnostics",new JsonArray());var result=new JsonObject();result.addProperty("digest",Canonical.digest(content,"canonical"));var vs=new JsonArray();visited.forEach(vs::add);result.add("visited",vs);out.add("output",result);return out;
  }catch(Exception ignored){return failure(id,code);}
 }
 public static void main(String[] args)throws Exception {var in=new BufferedInputStream(System.in);for(;;){var b=new ByteArrayOutputStream();boolean over=false;int c;while((c=in.read())!=-1&&c!=10){if(b.size()<=LIMIT)b.write(c);else over=true;}if(c==-1&&b.size()==0)return;System.out.println(Canonical.encode(execute(b.toByteArray())));System.out.flush();}}
}
