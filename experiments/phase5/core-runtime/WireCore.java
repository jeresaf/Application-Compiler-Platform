import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.*;
/** Immutable request strings/list copies; framework values stop at the wire adapter. */
public final class WireCore {
 record Request(String id,String protocol,String canonical,List<String> provenance,List<String> obligations,Map<String,List<String>> dependencies,int budget,boolean cancelled,String portVersion) {
  Request {provenance=List.copyOf(provenance);obligations=List.copyOf(obligations);var copy=new HashMap<String,List<String>>();dependencies.forEach((k,v)->copy.put(k,List.copyOf(v)));dependencies=Map.copyOf(copy);}
 }
 static List<String> records(JsonArray a){var r=new ArrayList<String>();for(var v:a)r.add(Canonical.encode(v));return r;}
 static JsonArray array(List<String> values){var r=new JsonArray();for(var v:values)r.add(JsonParser.parseString(v));return r;}
 static Request parse(JsonObject r){var graph=new HashMap<String,List<String>>();for(var e:r.getAsJsonObject("dependencies").entrySet()){var next=new ArrayList<String>();for(var v:e.getValue().getAsJsonArray())next.add(v.getAsString());graph.put(e.getKey(),next);}return new Request(r.get("id").getAsString(),r.get("protocol").getAsString(),r.get("canonicalInput").getAsString(),records(r.getAsJsonArray("provenance")),records(r.getAsJsonArray("obligations")),graph,r.get("budget").getAsInt(),r.get("cancelled").getAsBoolean(),r.get("portVersion").getAsString());}
 sealed interface Result permits Success,Failure {}
 record Success(List<String> visited) implements Result {Success{visited=List.copyOf(visited);}}
 record Failure(String code) implements Result {}
 interface Port {List<String> successors(String subject);}
 static Result traverse(Request r)throws Exception {var visited=new ArrayList<String>();String code="";
  if(!r.protocol().equals("acp-core-wire/1"))code="VERSION";
  else if(!r.portVersion().equals("graph/1"))code="PORT";
  else if(!Canonical.encode(Canonical.parse(r.canonical().getBytes(StandardCharsets.UTF_8))).equals(r.canonical()))code="CANONICAL";
  Port port=s->r.dependencies().getOrDefault(s,List.of());var pending=new ArrayDeque<String>();pending.add("ROOT");
  while(code.isEmpty()&&!pending.isEmpty()){String id=pending.remove();if(r.cancelled()){code="CANCELLED";break;}if(visited.contains(id))continue;if(visited.size()>=r.budget()){code="RESOURCE";break;}visited.add(id);pending.addAll(port.successors(id));}
  return code.isEmpty()?new Success(visited):new Failure(code);
 }
 static JsonObject execute(Request r)throws Exception {Result result=traverse(r);var out=new JsonObject();out.addProperty("protocol","acp-core-wire/1");out.addProperty("id",r.id());out.addProperty("status",result instanceof Success?"SUCCESS":"FAILURE");var diagnostics=new JsonArray();if(result instanceof Failure f){var d=new JsonObject();d.addProperty("code",f.code());d.addProperty("subject","ROOT");d.addProperty("primary","graph.acp#L1C1");d.add("related",new JsonArray());d.addProperty("remediation","Repair the declared request or retry with valid authority and budgets.");diagnostics.add(d);}out.add("diagnostics",diagnostics);if(result instanceof Failure)return out;var success=(Success)result;out.addProperty("digest",Canonical.digest(Canonical.parse(r.canonical().getBytes(StandardCharsets.UTF_8)),"canonical"));out.add("provenance",array(r.provenance()));out.add("obligations",array(r.obligations()));var visited=new JsonArray();success.visited().forEach(visited::add);out.add("visited",visited);out.addProperty("work",success.visited().size());return out;}
 public static void main(String[] args)throws Exception {var input=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));for(String line;(line=input.readLine())!=null;){long start=System.nanoTime();Request request=parse(Canonical.parse(line.getBytes(StandardCharsets.UTF_8)).getAsJsonObject());long decoded=System.nanoTime();String out=Canonical.encode(execute(request));System.out.println(out);if(System.getenv("ACP_WIRE_METRICS")!=null)System.err.println("{\"decodeNs\":"+(decoded-start)+",\"executeEncodeNs\":"+(System.nanoTime()-decoded)+",\"inputBytes\":"+line.getBytes(StandardCharsets.UTF_8).length+",\"outputBytes\":"+out.getBytes(StandardCharsets.UTF_8).length+"}");}}
}
