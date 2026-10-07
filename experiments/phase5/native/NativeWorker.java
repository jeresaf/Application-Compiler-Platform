import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import com.google.gson.*;
/** True native JVM worker: parser classes and Xtext injector survive requests. */
public final class NativeWorker {
 static final int LIMIT=1048576;
 static final String PROTOCOL="acp-frontend-wire/1";
 static JsonObject parse(String candidate,String text)throws Exception{return candidate.equals("antlr")?Probe.parse(text,1):XtextProbe.parse(text,1);}
 static String identity(String candidate){return "acp-experiment-"+candidate+"/"+(candidate.equals("antlr")?"4.13.2":"2.44.0");}
 static String hash(JsonElement value)throws Exception{return ""+HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Canonical.encode(value).getBytes(StandardCharsets.UTF_8)));}
 static JsonObject clean(JsonObject output){var result=new JsonObject();for(String key:List.of("candidate","module","imports","exports","model","spans","errors"))if(output.has(key))result.add(key,output.get(key));for(var e:result.getAsJsonArray("errors"))e.getAsJsonObject().remove("message");return result;}
 static byte[] line(InputStream input)throws IOException{var out=new ByteArrayOutputStream();for(int b;(b=input.read())!=-1;){if(b==10)return out.toByteArray();if(out.size()>=LIMIT)throw new IOException("INPUT_SIZE");out.write(b);}return out.size()==0?null:out.toByteArray();}
 public static void main(String[] args)throws Exception {
  if(args[0].equals("--embedded")){String candidate=args[1],text=Files.readString(Path.of(args[2]));var times=new JsonArray();String expected=null;for(int i=0;i<6;i++){long start=System.nanoTime();var output=clean(parse(candidate,text));times.add((System.nanoTime()-start)/1000);String digest=hash(output);if(expected==null)expected=digest;else if(!expected.equals(digest))throw new AssertionError("Shared parser state");}var result=new JsonObject();result.add("directCallMicroseconds",times);result.addProperty("semanticDigest",expected);result.addProperty("pid",ProcessHandle.current().pid());System.out.println(result);return;}
  String candidate=args[0];var seen=new HashSet<String>();int sequence=0;
  var input=new BufferedInputStream(System.in);
  for(byte[] raw;(raw=line(input))!=null;){JsonObject request=new JsonObject();JsonObject payload=new JsonObject();String status="SUCCESS";
   long start=System.nanoTime();
   try {
    request=Canonical.parse(raw).getAsJsonObject();
    if(!request.keySet().equals(Set.of("protocol","frontend","id","source")))throw new IllegalArgumentException("MALFORMED_REQUEST");
    if(!request.get("protocol").getAsString().equals(PROTOCOL))throw new IllegalArgumentException("PROTOCOL_VERSION");
    if(!request.get("frontend").getAsString().equals(identity(candidate)))throw new IllegalArgumentException("FRONTEND_VERSION");
    String id=request.get("id").getAsString();if(id.isEmpty()||id.length()>128)throw new IllegalArgumentException("REQUEST_ID");if(!seen.add(id))throw new IllegalArgumentException("DUPLICATE_ID");if(seen.size()>1024)throw new IllegalArgumentException("SESSION_LIMIT");
    var source=request.getAsJsonObject("source");if(!source.get("version").getAsString().equals("acp-text/1")||!source.get("frontend").getAsString().equals(identity(candidate)))throw new IllegalArgumentException("FRONTEND_VERSION");
    var documents=source.getAsJsonArray("documents");if(documents.isEmpty()||documents.size()>128)throw new IllegalArgumentException("MALFORMED_REQUEST");var outputs=new JsonArray();
    for(var item:documents){var doc=item.getAsJsonObject();var output=new JsonObject();output.add("path",doc.get("path"));output.add("output",clean(parse(candidate,doc.get("text").getAsString())));outputs.add(output);}
    payload.add("documents",outputs);var metrics=new JsonObject();metrics.addProperty("pid",ProcessHandle.current().pid());metrics.addProperty("sequence",++sequence);metrics.addProperty("nativeRequestMicroseconds",(System.nanoTime()-start)/1000);metrics.addProperty("heapUsedBytes",Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory());payload.add("metrics",metrics);
   }catch(Exception error){status="FAILURE";String code=error.getMessage();if(!Set.of("MALFORMED_REQUEST","PROTOCOL_VERSION","FRONTEND_VERSION","REQUEST_ID","DUPLICATE_ID","SESSION_LIMIT").contains(code==null?"":code))code="FRONTEND_FAILURE";payload=new JsonObject();payload.addProperty("code",code);}
   var response=new JsonObject();response.addProperty("protocol",PROTOCOL);response.addProperty("frontend",identity(candidate));response.add("id",request.get("id"));response.addProperty("requestDigest",hash(request));response.addProperty("status",status);response.add("payload",payload);
   String encoded=Canonical.encode(response);if(encoded.getBytes(StandardCharsets.UTF_8).length+1>LIMIT){response.addProperty("status","FAILURE");var failure=new JsonObject();failure.addProperty("code","RESPONSE_SIZE");response.add("payload",failure);encoded=Canonical.encode(response);}System.out.println(encoded);System.out.flush();
  }
 }
}
