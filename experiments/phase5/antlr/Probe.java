import java.nio.file.*;
import java.util.*;
import org.antlr.v4.runtime.*;
import com.google.gson.*;

/** Experimental parser-to-plain-JSON boundary; never imported by the compiler. */
public final class Probe {
    static final Gson JSON = new GsonBuilder().serializeNulls().create();
    static JsonElement value(AcpParser.ValueContext v) {
        if (v.object()!=null) return object(v.object());
        if (v.array()!=null) { var a=new JsonArray(); for(var x:v.array().value()) a.add(value(x)); return a; }
        String first=v.getChild(0).getText();
        if(first.equals("ref")) { var o=new JsonObject(); o.add("id",JSON.fromJson(v.STRING(0).getText(),JsonElement.class)); o.addProperty("revision",Long.parseLong(v.INT(0).getText())); return o; }
        if(first.equals("Money")) {var o=new JsonObject(); o.addProperty("kind","Money"); o.add("currency",JSON.fromJson(v.STRING(0).getText(),JsonElement.class)); o.addProperty("precision",Long.parseLong(v.INT(0).getText())); o.addProperty("scale",Long.parseLong(v.INT(1).getText())); o.add("rounding",JSON.fromJson(v.STRING(1).getText(),JsonElement.class)); return o;}
        return JSON.fromJson(first,JsonElement.class);
    }
    static void identityBody(JsonObject node) {for(String key:new String[]{"kind","id","revision"})if(node.has(key))throw new IllegalArgumentException("Reserved declaration identity in body");}
    static JsonObject object(AcpParser.ObjectContext o) {
        var result=new JsonObject();
        for(int i=0;i<o.STRING().size();i++) {String key=JSON.fromJson(o.STRING(i).getText(),String.class); if(result.has(key)) throw new IllegalArgumentException("Duplicate object key"); result.add(key,value(o.value(i)));}
        return result;
    }
    public static JsonObject parse(String text,int runs) throws Exception {
        long start=System.nanoTime();
        var errors=new JsonArray(); var measurements=new JsonArray(); AcpParser.DocumentContext doc=null;
        var listener=new BaseErrorListener(){public void syntaxError(Recognizer<?,?> r,Object symbol,int line,int col,String msg,RecognitionException e){var error=new JsonObject(); error.addProperty("line",line);error.addProperty("column",col);error.addProperty("message",msg);errors.add(error);}};
        for(int i=0;i<runs;i++) {
            long parse=System.nanoTime(); var lexer=new AcpLexer(CharStreams.fromString(text)); lexer.removeErrorListeners();lexer.addErrorListener(listener);
            var parser=new AcpParser(new CommonTokenStream(lexer));parser.removeErrorListeners();parser.addErrorListener(listener);doc=parser.document();measurements.add((System.nanoTime()-parse)/1e6);
        }
        var response=new JsonObject(); response.addProperty("candidate","ANTLR 4.13.2 / Java 21");response.add("errors",errors);response.add("parseMs",measurements);var imports=new JsonArray();if(!doc.STRING().isEmpty()){response.add("module",JSON.fromJson(doc.STRING(0).getText(),JsonElement.class));for(int i=1;i<doc.STRING().size();i++)imports.add(JSON.fromJson(doc.STRING(i).getText(),JsonElement.class));}response.add("imports",imports);var exports=new JsonArray();for(var d:doc.declaration())if(d.start.getText().equals("export"))exports.add(JSON.fromJson(d.STRING().getText(),JsonElement.class));response.add("exports",exports);
        if(errors.isEmpty() && !"1".equals(System.getenv("ACP_PARSE_ONLY"))) {
            var model=object(doc.object());var nodes=new JsonArray();var spans=new JsonArray();
            for(var d:doc.declaration()) {var node=object(d.object());identityBody(node);node.addProperty("kind",d.ID().getText());node.add("id",JSON.fromJson(d.STRING().getText(),JsonElement.class));node.addProperty("revision",Long.parseLong(d.INT().getText()));nodes.add(node);var span=new JsonObject();span.add("id",node.get("id"));span.addProperty("line",d.start.getLine());span.addProperty("column",d.start.getCharPositionInLine());span.addProperty("endLine",d.stop.getLine());span.addProperty("endColumn",d.stop.getCharPositionInLine()+d.stop.getText().length());spans.add(span);}
            model.add("nodes",nodes);response.add("model",model);response.add("spans",spans);
        }
        response.addProperty("elapsedMs",(System.nanoTime()-start)/1e6);return response;
    }
    public static void main(String[] args)throws Exception {System.out.println(JSON.toJson(parse(Files.readString(Path.of(args[0])),Integer.parseInt(args.length>1?args[1]:"1"))));}
}
