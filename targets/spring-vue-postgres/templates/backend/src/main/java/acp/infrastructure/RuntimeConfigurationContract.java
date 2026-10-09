package acp.infrastructure;

import java.net.URI;
import org.springframework.core.env.Environment;

/** Deployment-owned configuration. Validation precedes activation or polling. */
public final class RuntimeConfigurationContract {
    public static final String VERSION="acp-runtime-configuration/1.0.0";
    private RuntimeConfigurationContract() {}
    private static String required(Environment env,String key) {
        String value=env.getProperty(key);
        if(value==null || value.isBlank() || value.contains("${"))throw new IllegalStateException("RUNTIME_CONFIGURATION_REQUIRED:"+key);
        return value;
    }
    public static void validate(Environment env,TargetModel model,boolean transportBound) {
        if(!VERSION.equals(required(env,"acp.runtime.configuration-contract")))throw new IllegalStateException("RUNTIME_CONFIGURATION_VERSION");
        String mode=required(env,"acp.runtime.mode");
        if(!mode.equals("production") && !mode.equals("development"))throw new IllegalStateException("RUNTIME_MODE");
        String database=required(env,"spring.datasource.url");
        if(!database.startsWith("jdbc:postgresql://"))throw new IllegalStateException("RUNTIME_POSTGRESQL_REQUIRED");
        required(env,"spring.datasource.username");required(env,"spring.datasource.password");
        URI issuer=URI.create(required(env,"spring.security.oauth2.resourceserver.jwt.issuer-uri"));
        if(issuer.getHost()==null || (!"https".equals(issuer.getScheme()) && !(mode.equals("development") && "http".equals(issuer.getScheme()) && java.util.Set.of("localhost","127.0.0.1","[::1]").contains(issuer.getHost()))))throw new IllegalStateException("RUNTIME_OIDC_ISSUER");
        required(env,"spring.security.oauth2.resourceserver.jwt.audiences");
        if(!"2026d".equals(required(env,"acp.runtime.timezone-artifact")) || RuntimeConfigurationContract.class.getResource("/acp-tzdb-2026d.json")==null)throw new IllegalStateException("RUNTIME_TIMEZONE_ARTIFACT");
        if(!"single-instance-postgresql-claims".equals(required(env,"acp.runtime.scheduler-profile")))throw new IllegalStateException("RUNTIME_SCHEDULER_PROFILE");
        String delivery=required(env,"acp.runtime.delivery");
        if(!java.util.Set.of("active","disabled").contains(delivery))throw new IllegalStateException("RUNTIME_DELIVERY_MODE");
        if(!model.nodes("DeliveryPolicy").isEmpty() && !delivery.equals("active"))throw new IllegalStateException("RUNTIME_REQUIRED_DELIVERY_DISABLED");
        if(delivery.equals("active") && !transportBound)throw new IllegalStateException("TRANSPORT_ADAPTER_REQUIRED");
        if(mode.equals("production")) {
            if(!"trusted-tls-proxy".equals(required(env,"acp.runtime.deployment-profile")) || !"framework".equals(required(env,"server.forward-headers-strategy")) || !"true".equals(required(env,"acp.runtime.trusted-proxy-network")))throw new IllegalStateException("RUNTIME_TLS_PROXY_PROFILE");
            if(!"true".equals(env.getProperty("acp.runtime.poll-enabled","true")))throw new IllegalStateException("RUNTIME_PRODUCTION_POLL_REQUIRED");
        }
    }
}
