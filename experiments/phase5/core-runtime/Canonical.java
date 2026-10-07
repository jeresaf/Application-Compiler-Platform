import java.io.*;
import java.nio.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import com.google.gson.*;
import com.google.gson.stream.*;

/** Strict accepted-profile interoperability probe, independent of Python. */
public final class Canonical {
 static String valid(String s){for(int i=0;i<s.length();i++){char c=s.charAt(i);if(Character.isHighSurrogate(c)){if(++i>=s.length()||!Character.isLowSurrogate(s.charAt(i)))throw new IllegalArgumentException("surrogate");}else if(Character.isLowSurrogate(c))throw new IllegalArgumentException("surrogate");}return s;}
 static JsonElement value(JsonReader r,int depth)throws Exception {
  if(depth>48)throw new IllegalArgumentException("depth");
  switch(r.peek()){
   case BEGIN_OBJECT: {r.beginObject();var o=new JsonObject();while(r.hasNext()){String k=valid(r.nextName());if(o.has(k))throw new IllegalArgumentException("duplicate");o.add(k,value(r,depth+1));}r.endObject();return o;}
   case BEGIN_ARRAY: {r.beginArray();var a=new JsonArray();while(r.hasNext())a.add(value(r,depth+1));r.endArray();return a;}
   case STRING:return new JsonPrimitive(valid(r.nextString()));
   case NUMBER:{String token=r.nextString();if(!token.matches("-?(0|[1-9][0-9]*)"))throw new IllegalArgumentException("integer");long n=Long.parseLong(token);if(n < -9007199254740991L || n > 9007199254740991L)throw new IllegalArgumentException("safe");return new JsonPrimitive(n);}
   case BOOLEAN:return new JsonPrimitive(r.nextBoolean());
   case NULL:r.nextNull();return JsonNull.INSTANCE;
   default:throw new IllegalArgumentException("token");
  }
 }
 static JsonElement parse(byte[] raw)throws Exception {
  if(raw.length>1048576)throw new IllegalArgumentException("size");
  String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
  if(text.startsWith("\ufeff"))throw new IllegalArgumentException("bom");
  var reader=new JsonReader(new StringReader(text));reader.setStrictness(Strictness.STRICT);var v=value(reader,0);if(reader.peek()!=JsonToken.END_DOCUMENT)throw new IllegalArgumentException("trailing");return v;
 }
 static String quote(String text){valid(text);var b=new StringBuilder("\"");for(char c:text.toCharArray()){switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\b':b.append("\\b");break;case '\t':b.append("\\t");break;case '\n':b.append("\\n");break;case '\f':b.append("\\f");break;case '\r':b.append("\\r");break;default:if(c<32)b.append(String.format(Locale.ROOT,"\\u%04x",(int)c));else b.append(c);}}return b.append('"').toString();}
 static String encode(JsonElement v){
  if(v.isJsonNull())return "null";
  if(v.isJsonArray()){var out=new ArrayList<String>();for(var x:v.getAsJsonArray())out.add(encode(x));return "["+String.join(",",out)+"]";}
  if(v.isJsonObject()){var keys=new ArrayList<>(v.getAsJsonObject().keySet());Collections.sort(keys);var out=new ArrayList<String>();for(String k:keys)out.add(quote(k)+":"+encode(v.getAsJsonObject().get(k)));return "{"+String.join(",",out)+"}";}
  var p=v.getAsJsonPrimitive();return p.isString()?quote(p.getAsString()):p.toString();
 }
 static String digest(JsonElement v,String domain)throws Exception {var h=MessageDigest.getInstance("SHA-256");h.update(("ACP\0acp-jcs-safe-v1\0"+domain+"\0").getBytes(StandardCharsets.UTF_8));h.update(encode(v).getBytes(StandardCharsets.UTF_8));return "sha256:"+HexFormat.of().formatHex(h.digest());}
 static void equal(String a,String b){if(!a.equals(b))throw new AssertionError(a+" != "+b);}
 public static void main(String[] args)throws Exception{
  Path root=Path.of(args[0]);var vectors=parse(Files.readAllBytes(root.resolve("byte-vectors.json"))).getAsJsonObject();
  for(var item:vectors.getAsJsonArray("positive")){var v=item.getAsJsonObject();var input=parse(v.get("input").getAsString().getBytes(StandardCharsets.UTF_8));equal(encode(input),v.get("canonical").getAsString());equal(digest(input,"vector"),v.get("digest").getAsString());}
  for(var item:vectors.getAsJsonArray("negative")){boolean rejected=false;try{parse(item.getAsJsonObject().get("input").getAsString().getBytes(StandardCharsets.UTF_8));}catch(Exception e){rejected=true;}if(!rejected)throw new AssertionError(item.toString());}
  for(byte[] raw:new byte[][]{new byte[]{(byte)255},new byte[1048577]}){boolean rejected=false;try{parse(raw);}catch(Exception e){rejected=true;}if(!rejected)throw new AssertionError();}
  var manifest=parse(Files.readAllBytes(root.resolve("manifest.json"))).getAsJsonObject();for(var item:manifest.getAsJsonArray("examples")){var v=item.getAsJsonObject();var snapshot=parse(Files.readAllBytes(root.resolve(v.get("file").getAsString()))).getAsJsonObject();equal(digest(snapshot.get("content"),"canonical"),v.get("contentDigest").getAsString());}
  System.out.println("{\"candidate\":\"Java 21 / Gson 2.13.2 strict adapter\",\"status\":\"PASS\",\"positive\":"+vectors.getAsJsonArray("positive").size()+",\"negative\":"+vectors.getAsJsonArray("negative").size()+",\"snapshotHashes\":"+manifest.getAsJsonArray("examples").size()+"}");
 }
}
