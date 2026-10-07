import javax.tools.*;
import javax.lang.model.element.*;
import javax.lang.model.type.TypeKind;
import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** javac semantic bindings, no syntax-only resolution claims. */
public class NativeSource {
 public static void main(String[] args)throws Exception {
  var compiler=ToolProvider.getSystemJavaCompiler();var diagnostics=new DiagnosticCollector<JavaFileObject>();
  try(var files=compiler.getStandardFileManager(diagnostics,null,null)) {
   var task=(JavacTask)compiler.getTask(null,files,diagnostics,List.of("-proc:none"),null,files.getJavaFileObjects(args));
   var parsed=new ArrayList<CompilationUnitTree>();task.parse().forEach(parsed::add);task.analyze();var trees=Trees.instance(task);var findings=new JsonArray();
   for(var unit:parsed) new TreePathScanner<Void,Void>() {
    public Void visitMethodInvocation(MethodInvocationTree node,Void unused){var e=trees.getElement(getCurrentPath());var r=new JsonObject();r.addProperty("file",Path.of(unit.getSourceFile().toUri()).getFileName().toString());r.addProperty("name",node.getMethodSelect().toString());r.addProperty("status",e!=null&&e.getKind()==ElementKind.METHOD&&e.asType().getKind()!=TypeKind.ERROR?"KNOWN":"UNRESOLVED");r.addProperty("binding",e!=null&&e.getKind()==ElementKind.METHOD?e.toString():"");r.addProperty("start",trees.getSourcePositions().getStartPosition(unit,node));r.addProperty("end",trees.getSourcePositions().getEndPosition(unit,node));findings.add(r);return super.visitMethodInvocation(node,unused);}
   }.scan(unit,null);
   var out=new JsonObject();out.addProperty("analyzer","javac 21 Trees native semantic API");out.add("calls",findings);var errors=new JsonArray();for(var d:diagnostics.getDiagnostics()){var r=new JsonObject();r.addProperty("code",d.getCode());r.addProperty("line",d.getLineNumber());errors.add(r);}out.add("diagnostics",errors);out.addProperty("decorators","ABSENT");System.out.println(out);
  }
 }
}
