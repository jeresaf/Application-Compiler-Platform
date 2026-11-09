"""Test-only, bounded PostgreSQL lock pressure; never packaged in the application."""
from engineering.identity.fixture import adapter_source as parent
from engineering.source_intelligence.model import require
PRESSURE=62425160

def adapter_source():
    source=parent();marker='@GetMapping("/__test/facts")';require(source.count(marker)==1,'H6_FIXTURE_DRIFT')
    method='''
  final java.util.concurrent.ExecutorService h6Pressure=new java.util.concurrent.ThreadPoolExecutor(34,34,0,java.util.concurrent.TimeUnit.MILLISECONDS,new java.util.concurrent.ArrayBlockingQueue<Runnable>(34),new java.util.concurrent.ThreadPoolExecutor.AbortPolicy());
  @jakarta.annotation.PreDestroy void h6PressureClose(){h6Pressure.shutdownNow();try{if(!h6Pressure.awaitTermination(20,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("H6_PRESSURE_CLEANUP");}catch(InterruptedException e){Thread.currentThread().interrupt();}}
  @PostMapping("/__test/h6-pressure") Map<String,Object> h6Pressure(){
   for(int i=0;i<34;i++)h6Pressure.submit(()->{try(var connection=java.util.Objects.requireNonNull(jdbc.getDataSource()).getConnection()){
    connection.setAutoCommit(false);try(var statement=connection.createStatement()){statement.setQueryTimeout(15);statement.execute("SELECT pg_advisory_xact_lock(PRESSURE)");}finally{connection.rollback();}
   }catch(Exception failed){throw new IllegalStateException("H6_PRESSURE_FAILED");}});
   return Map.of("submitted",34);
  }
'''.replace('PRESSURE)',str(PRESSURE)+')')
    return source.replace(marker,method+marker)
