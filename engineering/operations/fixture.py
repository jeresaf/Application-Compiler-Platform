"""Test-only, bounded PostgreSQL lock pressure; never packaged in the application."""
from engineering.identity.fixture import adapter_source as parent
from engineering.source_intelligence.model import require
PRESSURE=62425160

def adapter_source():
    source=parent();marker='@GetMapping("/__test/facts")';require(source.count(marker)==1,'H6_FIXTURE_DRIFT')
    method='''
  final java.util.concurrent.ExecutorService h6Pressure=new java.util.concurrent.ThreadPoolExecutor(34,34,0,java.util.concurrent.TimeUnit.MILLISECONDS,new java.util.concurrent.ArrayBlockingQueue<Runnable>(34),new java.util.concurrent.ThreadPoolExecutor.AbortPolicy());
  final java.util.concurrent.atomic.AtomicBoolean h6PressureStarted=new java.util.concurrent.atomic.AtomicBoolean();
  final java.util.concurrent.ConcurrentLinkedQueue<String> h6PressureErrors=new java.util.concurrent.ConcurrentLinkedQueue<>();
  @GetMapping("/__test/h6-pressure-state") Map<String,Object> h6PressureState(){return Map.of("errors",java.util.List.copyOf(h6PressureErrors));}
  @jakarta.annotation.PreDestroy void h6PressureClose(){h6Pressure.shutdownNow();try{if(!h6Pressure.awaitTermination(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("H6_PRESSURE_CLEANUP");}catch(InterruptedException e){Thread.currentThread().interrupt();}}
  @PostMapping("/__test/h6-pressure") Map<String,Object> h6Pressure()throws Exception{
   if(!h6PressureStarted.compareAndSet(false,true))throw new IllegalStateException("H6_PRESSURE_ALREADY_STARTED");
   for(int i=0;i<34;i++){var acquired=new java.util.concurrent.CompletableFuture<Void>();h6Pressure.submit(()->{try(var connection=java.util.Objects.requireNonNull(jdbc.getDataSource()).getConnection()){
    connection.setAutoCommit(false);acquired.complete(null);try(var statement=connection.createStatement()){statement.setQueryTimeout(15);statement.execute("SELECT pg_advisory_xact_lock(PRESSURE)");}finally{connection.rollback();}
   }catch(Exception failed){h6PressureErrors.add(failed.getClass().getName()+":"+(failed instanceof java.sql.SQLException sql?sql.getSQLState():""));acquired.completeExceptionally(failed);throw new IllegalStateException("H6_PRESSURE_FAILED");}});acquired.get(2,java.util.concurrent.TimeUnit.SECONDS);}
   return Map.of("submitted",34);
  }
'''.replace('PRESSURE)',str(PRESSURE)+')')
    return source.replace(marker,method+marker)
