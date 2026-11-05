"""H4 test-only observation. Production handlers, authorization and outcomes are unchanged."""
from engineering.capacity.fixture import adapter_source as original
from engineering.source_intelligence.model import require


def adapter_source():
    source=original();marker='@Bean JwtDecoder decoder()'
    require(source.count(marker)==1,'H4_OBSERVER_DRIFT')
    observer='''
 @Bean ExceptionObserver h4ExceptionObserver(){return new ExceptionObserver();}
 static final class ExceptionObserver implements org.springframework.web.servlet.HandlerExceptionResolver,org.springframework.core.Ordered {
  public int getOrder(){return Integer.MIN_VALUE;}
  public org.springframework.web.servlet.ModelAndView resolveException(jakarta.servlet.http.HttpServletRequest request,jakarta.servlet.http.HttpServletResponse response,Object handler,Exception error){
   var seen=java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<Throwable,Boolean>());
   for(Throwable cause=error;cause!=null&&seen.add(cause);cause=cause.getCause())
    System.err.println("H4_EXCEPTION:"+cause.getClass().getName()+":"+(cause instanceof java.sql.SQLException sql?sql.getSQLState():""));
   return null; // Observation only. Existing handlers determine the response.
  }
 }
 '''
    return source.replace(marker,observer+marker,1)
