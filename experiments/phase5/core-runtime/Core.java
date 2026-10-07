import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Bounded typed graph-stage experiment, not the production kernel. */
public final class Core {
 record Subject(String id, int revision) {}
 record Diagnostic(String code, Subject subject, String locator) {}
 sealed interface Result permits Success, Failure {}
 record Success(List<Subject> visited) implements Result { Success {visited=List.copyOf(visited);} }
 record Failure(Diagnostic diagnostic) implements Result {}
 interface GraphPort { List<Subject> successors(Subject subject); }
 static Result traverse(Subject root, GraphPort port, int budget, AtomicBoolean cancelled) {
  var pending=new ArrayDeque<Subject>();var seen=new LinkedHashSet<Subject>();pending.add(root);
  while(!pending.isEmpty()) {var next=pending.remove();
   if(cancelled.get())return new Failure(new Diagnostic("CANCELLED",next,"corpus/graph#"+next.id()));
   if(seen.contains(next))continue;
   if(seen.size()>=budget)return new Failure(new Diagnostic("WORK_LIMIT",next,"corpus/graph#"+next.id()));
   seen.add(next);pending.addAll(port.successors(next));
  } return new Success(new ArrayList<>(seen));
 }
 public static void main(String[] args) throws Exception {
  int count=Integer.parseInt(args[0]);GraphPort port=s->{int i=Integer.parseInt(s.id());return i+1<count?List.of(new Subject(""+(i+1),1)):List.of();};
  var root=new Subject("0",1);var timings=new ArrayList<Double>();
  for(int i=0;i<8;i++){long start=System.nanoTime();var r=traverse(root,port,count,new AtomicBoolean());if(!(r instanceof Success s)||s.visited().size()!=count)throw new AssertionError();timings.add((System.nanoTime()-start)/1e6);}
  if(!(traverse(root,port,0,new AtomicBoolean()) instanceof Failure))throw new AssertionError();
  if(!(traverse(root,port,count,new AtomicBoolean(true)) instanceof Failure))throw new AssertionError();
  try(var workers=Executors.newVirtualThreadPerTaskExecutor()) {var tasks=new ArrayList<Future<Result>>();for(int i=0;i<8;i++)tasks.add(workers.submit(()->traverse(root,port,count,new AtomicBoolean())));for(var task:tasks)if(!(task.get() instanceof Success))throw new AssertionError();}
  System.out.println("{\"candidate\":\"Java 21\",\"nodes\":"+count+",\"graphMs\":"+timings+",\"cancellation\":true,\"workLimit\":true,\"concurrentRuns\":8,\"canonical\":\"NOT_RUN\"}");
 }
}
