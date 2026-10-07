import java.nio.file.*;
import java.io.*;
import com.google.gson.*;
import org.eclipse.emf.ecore.*;
import org.eclipse.emf.common.util.URI;
import org.eclipse.xtext.resource.*;
import org.eclipse.xtext.nodemodel.util.NodeModelUtils;
import org.eclipse.xtext.validation.*;
import org.eclipse.xtext.util.CancelIndicator;

/** Experimental EMF-to-plain-record adapter; EMF objects stop here. */
public final class XtextProbe {
 static final Gson JSON=new GsonBuilder().serializeNulls().create();
 static Object get(EObject o,String name){return o.eGet(o.eClass().getEStructuralFeature(name));}
 static String string(EObject o,String name){return (String)get(o,name);}
 @SuppressWarnings("unchecked") static Iterable<EObject> list(EObject o,String name){return (Iterable<EObject>)get(o,name);}
 static JsonElement plain(EObject o){
  switch(o.eClass().getName()){
   case "Object": {var r=new JsonObject();for(var p:list(o,"pairs")){String key=string(p,"key");if(r.has(key))throw new IllegalArgumentException("Duplicate object key");r.add(key,plain((EObject)get(p,"value")));}return r;}
   case "Array": {var r=new JsonArray();for(var v:list(o,"values"))r.add(plain(v));return r;}
   case "Text": return new JsonPrimitive(string(o,"value"));
   case "Number": return new JsonPrimitive((Number)get(o,"value"));
   case "Boolean": return new JsonPrimitive(string(o,"value").equals("true"));
   case "Null": return JsonNull.INSTANCE;
   case "Reference": {var r=new JsonObject();var feature=o.eClass().getEStructuralFeature("target");var nodes=NodeModelUtils.findNodesForFeature(o,feature);r.add("id",JSON.fromJson(NodeModelUtils.getTokenText(nodes.get(0)),JsonElement.class));r.addProperty("revision",(Number)get(o,"revision"));return r;}
   case "Money": {var r=new JsonObject();r.addProperty("kind","Money");for(String k:new String[]{"currency","rounding"})r.addProperty(k,string(o,k));for(String k:new String[]{"precision","scale"})r.addProperty(k,(Number)get(o,k));return r;}
   default:throw new IllegalArgumentException(o.eClass().getName());
  }
 }
 public static void main(String[] args)throws Exception{
  long startup=System.nanoTime();var setup=new org.acp.experiment.AcpStandaloneSetup(){
   @Override public com.google.inject.Injector createInjector(){return com.google.inject.Guice.createInjector(org.eclipse.xtext.util.Modules2.mixin(new org.acp.experiment.AcpRuntimeModule(),new org.acp.experiment.ide.AcpIdeModule()));}
  };var injector=setup.createInjectorAndDoEMFRegistration();double startupMs=(System.nanoTime()-startup)/1e6;
  String text=Files.readString(Path.of(args[0]));var times=new JsonArray();XtextResource resource=null;
  for(int i=0;i<Integer.parseInt(args.length>1?args[1]:"1");i++){
   var set=injector.getInstance(XtextResourceSet.class);resource=(XtextResource)set.createResource(URI.createURI("memory:/experiment.acp"));long start=System.nanoTime();resource.load(new ByteArrayInputStream(text.getBytes(java.nio.charset.StandardCharsets.UTF_8)),null);times.add((System.nanoTime()-start)/1e6);
  }
  var output=new JsonObject();output.addProperty("candidate","Xtext 2.44.0 / Java 21");output.addProperty("startupMs",startupMs);output.add("parseMs",times);var errors=new JsonArray();
  for(var e:resource.getErrors()){var d=new JsonObject();d.addProperty("message",e.getMessage());d.addProperty("line",e.getLine());d.addProperty("column",e.getColumn());errors.add(d);}output.add("errors",errors);
  if(errors.isEmpty()&&!"1".equals(System.getenv("ACP_PARSE_ONLY"))){var doc=resource.getContents().get(0);var model=plain((EObject)get(doc,"header")).getAsJsonObject();var nodes=new JsonArray();var spans=new JsonArray();
   for(var declaration:list(doc,"declarations")){var node=plain((EObject)get(declaration,"body")).getAsJsonObject();for(String key:new String[]{"kind","id","revision"})if(node.has(key))throw new IllegalArgumentException("Reserved declaration identity in body");node.addProperty("kind",string(declaration,"kind"));node.addProperty("id",string(declaration,"name"));node.addProperty("revision",(Number)get(declaration,"revision"));nodes.add(node);var span=new JsonObject();var n=NodeModelUtils.getNode(declaration);span.add("id",node.get("id"));span.addProperty("offset",n.getOffset());span.addProperty("length",n.getLength());span.addProperty("line",n.getStartLine());spans.add(span);}model.add("nodes",nodes);output.add("model",model);output.add("spans",spans);
   if("1".equals(System.getenv("ACP_EDITOR"))){long start=System.nanoTime();var issues=injector.getInstance(IResourceValidator.class).validate(resource,CheckMode.ALL,CancelIndicator.NullImpl);output.addProperty("nativeValidationMs",(System.nanoTime()-start)/1e6);output.addProperty("nativeIssueCount",issues.size());
    var factory=injector.getInstance(org.eclipse.xtext.ide.editor.contentassist.antlr.ContentAssistContextFactory.class);
    try(var pool=java.util.concurrent.Executors.newSingleThreadExecutor()){
     factory.setPool(pool);int offset=text.indexOf("ref ")+4;start=System.nanoTime();
     var contexts=factory.create(text,new org.eclipse.xtext.util.TextRegion(offset,0),offset,resource);
     var acceptor=injector.getInstance(org.eclipse.xtext.ide.editor.contentassist.IdeContentProposalAcceptor.class);acceptor.setCancelIndicator(CancelIndicator.NullImpl);
     injector.getInstance(org.eclipse.xtext.ide.editor.contentassist.IdeContentProposalProvider.class).createProposals(java.util.Arrays.asList(contexts),acceptor);
     output.addProperty("nativeCompletionMs",(System.nanoTime()-start)/1e6);int count=0;for(var entry:acceptor.getEntries())count++;output.addProperty("nativeCompletionCount",count);
    }
    start=System.nanoTime();int resolved=0,uses=0;var contents=resource.getAllContents();while(contents.hasNext()){var e=contents.next();if(e.eClass().getName().equals("Reference")){var target=(EObject)get(e,"target");if(!target.eIsProxy()){resolved++;uses+=org.eclipse.emf.ecore.util.EcoreUtil.UsageCrossReferencer.find(target,resource).size();}}}output.addProperty("nativeLinkNavigationMs",(System.nanoTime()-start)/1e6);output.addProperty("nativeResolvedReferences",resolved);output.addProperty("nativeUsageResultsIncludingRepeatedTargets",uses);
    start=System.nanoTime();resource.update(text.length(),0,"\n");output.addProperty("nativeIncrementalWhitespaceEditMs",(System.nanoTime()-start)/1e6);
    output.addProperty("rename","NOT_RUN: stable-ID aware source edits missing");output.addProperty("imports","NOT_SUPPORTED: no module visibility policy");
   }
  }System.out.println(JSON.toJson(output));
 }
}
