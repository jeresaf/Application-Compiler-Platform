import javax.tools.*;
import javax.lang.model.element.*;
import javax.lang.model.type.*;
import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.nio.file.*;
import java.util.*;

/** Versioned plain records from javac Trees/Elements; annotation processing disabled. */
public class NativeSource {
 static Path root; static Trees trees; static String text; static CompilationUnitTree unit;
 static List<Map<String,Object>> definitions=new ArrayList<>(),references=new ArrayList<>(),relations=new ArrayList<>(),literals=new ArrayList<>(),errors=new ArrayList<>();
 static Map<Element,String> local=new HashMap<>();
 static Map<String,Object> row(Object...pairs){var m=new LinkedHashMap<String,Object>();for(int i=0;i<pairs.length;i+=2)m.put((String)pairs[i],pairs[i+1]);return m;}
 static String key(Element e){if(e==null)return "";if(e instanceof QualifiedNameable q)return e.getKind()+":"+q.getQualifiedName();return key(e.getEnclosingElement())+"#"+e.getKind()+":"+e.toString();}
 static String file(){return root.relativize(Path.of(unit.getSourceFile().toUri()).toAbsolutePath().normalize()).toString().replace('\\','/');}
 static long start(Tree t){return trees.getSourcePositions().getStartPosition(unit,t);} static long end(Tree t){return trees.getSourcePositions().getEndPosition(unit,t);}
 static Element element(TreePath p){try{return trees.getElement(p);}catch(RuntimeException e){return null;}}
 static boolean valid(Element e){try{return e!=null && e.asType().getKind()!=TypeKind.ERROR;}catch(RuntimeException x){return false;}}
 static String target(Element e){return local.getOrDefault(e,"external:"+key(e));}
 static boolean bad(long a,long b){return errors.stream().anyMatch(d->file().equals(d.get("file")) && ((Number)d.get("start")).longValue()>=0 && ((Number)d.get("start")).longValue()<b && ((Number)d.get("end")).longValue()>=a);}
 static String owner(TreePath p){for(var q=p.getParentPath();q!=null;q=q.getParentPath()){if(!(q.getLeaf() instanceof ClassTree || q.getLeaf() instanceof MethodTree || q.getLeaf() instanceof VariableTree || q.getLeaf() instanceof TypeParameterTree))continue;var e=element(q);if(local.containsKey(e))return local.get(e);}return null;}
 static void reference(Tree node,TreePath p,String kind){
  var e=element(p);long a=start(node),b=end(node);boolean known=valid(e)&&!bad(a,b);
  if(a<0||b<a)return;
  var r=row("kind",kind,"file",file(),"start",a,"end",b,"from",owner(p),"to",known?target(e):null,"native",known?key(e):null,"confidence",known?"KNOWN":"UNRESOLVED");references.add(r);
 }
 static String json(Object v){if(v==null)return "null";if(v instanceof String s){var b=new StringBuilder("\"");for(char c:s.toCharArray()){switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default:if(c<32||Character.isSurrogate(c))b.append(String.format("\\u%04x",(int)c));else b.append(c);}}return b.append('"').toString();}if(v instanceof Map<?,?> m){var a=new ArrayList<String>();m.forEach((k,x)->a.add(json(k)+":"+json(x)));return "{"+String.join(",",a)+"}";}if(v instanceof Iterable<?> list){var a=new ArrayList<String>();list.forEach(x->a.add(json(x)));return "["+String.join(",",a)+"]";}return v.toString();}
 public static void main(String[] args)throws Exception{
  root=Path.of(args[0]).toAbsolutePath().normalize();var diagnostics=new DiagnosticCollector<JavaFileObject>();var compiler=ToolProvider.getSystemJavaCompiler();
  try(var manager=compiler.getStandardFileManager(diagnostics,Locale.ROOT,java.nio.charset.StandardCharsets.UTF_8)){
   var paths=Files.readAllLines(Path.of(args[2])).stream().map(root::resolve).map(Path::toFile).toList();
   var options=List.of("-proc:none","--release","21","-encoding","UTF-8","-classpath",args[1],"-sourcepath",args[3], "-implicit:none");
   var task=(JavacTask)compiler.getTask(null,manager,diagnostics,options,null,manager.getJavaFileObjectsFromFiles(paths));
   var units=new ArrayList<CompilationUnitTree>();task.parse().forEach(units::add);try{task.analyze();}catch(RuntimeException x){errors.add(row("code","ANALYZE_FAILED","file","","start",0,"end",0,"message",x.getClass().getSimpleName()));}
   trees=Trees.instance(task);
   for(var d:diagnostics.getDiagnostics())if(d.getKind()==Diagnostic.Kind.ERROR){String f=d.getSource()==null?"":root.relativize(Path.of(d.getSource().toUri())).toString().replace('\\','/');errors.add(row("code",d.getCode(),"file",f,"start",d.getStartPosition(),"end",d.getEndPosition(),"message",d.getMessage(Locale.ROOT)));}
   for(var u:units){unit=u;text=Files.readString(Path.of(u.getSourceFile().toUri()));
    definitions.add(row("key","module:"+file(),"kind","MODULE","name",u.getPackageName()==null?"":u.getPackageName().toString(),"native",u.getPackageName()==null?"":u.getPackageName().toString(),"file",file(),"start",0,"end",text.length(),"type","","container",null,"confidence","KNOWN"));
    new TreePathScanner<Void,Void>(){
     void define(Tree node){var e=element(getCurrentPath());if(!valid(e)||start(node)<0||end(node)<start(node))return;String id=file()+":"+start(node)+":"+key(e);local.put(e,id);definitions.add(row("key",id,"kind",e.getKind().toString(),"name",e.getSimpleName().toString(),"native",key(e),"file",file(),"start",start(node),"end",end(node),"type",e.asType().toString(),"container",local.get(e.getEnclosingElement()),"confidence",bad(start(node),end(node))?"UNKNOWN":"KNOWN"));if(e instanceof VariableElement v && v.getConstantValue() instanceof String value)literals.add(row("symbol",id,"value",value,"revision",null,"file",file(),"start",start(node),"end",end(node),"basis","NATIVE_CONSTANT_VALUE"));}
     @Override public Void visitClass(ClassTree n,Void x){define(n);return super.visitClass(n,x);}
     @Override public Void visitMethod(MethodTree n,Void x){define(n);return super.visitMethod(n,x);}
     @Override public Void visitVariable(VariableTree n,Void x){define(n);return super.visitVariable(n,x);}
     @Override public Void visitTypeParameter(TypeParameterTree n,Void x){define(n);return super.visitTypeParameter(n,x);}
    }.scan(u,null);
   }
   for(var u:units){unit=u;
    new TreePathScanner<Void,Void>(){
     @Override public Void visitIdentifier(IdentifierTree n,Void x){reference(n,getCurrentPath(),"REFERENCE");return super.visitIdentifier(n,x);}
     @Override public Void visitMemberSelect(MemberSelectTree n,Void x){reference(n,getCurrentPath(),"REFERENCE");return super.visitMemberSelect(n,x);}
     @Override public Void visitMethodInvocation(MethodInvocationTree n,Void x){reference(n,getCurrentPath(),"CALL");return super.visitMethodInvocation(n,x);}
     @Override public Void visitNewClass(NewClassTree n,Void x){reference(n,getCurrentPath(),"CONSTRUCT");return super.visitNewClass(n,x);}
     @Override public Void visitMemberReference(MemberReferenceTree n,Void x){reference(n,getCurrentPath(),"CALL_REFERENCE");return super.visitMemberReference(n,x);}
     @Override public Void visitLiteral(LiteralTree n,Void x){if(n.getValue() instanceof String value && owner(getCurrentPath())!=null)literals.add(row("symbol",owner(getCurrentPath()),"value",value,"revision",null,"file",file(),"start",start(n),"end",end(n),"basis","NATIVE_LITERAL_REFERENCE"));return super.visitLiteral(n,x);}
     @Override public Void visitImport(ImportTree n,Void x){reference(n,new TreePath(getCurrentPath(),n.getQualifiedIdentifier()),"IMPORT");return super.visitImport(n,x);}
     @Override public Void visitClass(ClassTree n,Void x){var e=element(getCurrentPath());if(e instanceof TypeElement t && local.containsKey(e)){
       var types=new ArrayList<TypeMirror>();if(t.getSuperclass().getKind()!=TypeKind.NONE)types.add(t.getSuperclass());types.addAll(t.getInterfaces());
       for(var type:types){var dest=type instanceof DeclaredType dt?dt.asElement():null;relations.add(row("kind",t.getInterfaces().contains(type)&&t.getKind()!=ElementKind.INTERFACE?"IMPLEMENTS":"EXTENDS","file",file(),"start",start(n),"end",end(n),"from",local.get(e),"to",valid(dest)?target(dest):null,"native",valid(dest)?key(dest):null,"confidence",valid(dest)&&!bad(start(n),end(n))?"KNOWN":"UNRESOLVED"));}
      }return super.visitClass(n,x);}
    }.scan(u,null);
   }
   System.out.println(json(row("protocol","acp-source-native/1","language","JAVA","definitions",definitions,"references",references,"relations",relations,"literals",literals,"diagnostics",errors,"toolVersion",System.getProperty("java.runtime.version"))));
  }
 }
}
