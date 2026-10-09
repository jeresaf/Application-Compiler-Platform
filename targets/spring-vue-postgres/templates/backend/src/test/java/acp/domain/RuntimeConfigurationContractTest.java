package acp.domain;

import acp.infrastructure.*;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;
import static org.junit.jupiter.api.Assertions.*;

class RuntimeConfigurationContractTest {
    MockEnvironment production(){return new MockEnvironment()
        .withProperty("acp.runtime.configuration-contract",RuntimeConfigurationContract.VERSION)
        .withProperty("acp.runtime.mode","production")
        .withProperty("spring.datasource.url","jdbc:postgresql://localhost/disposable")
        .withProperty("spring.datasource.username","disposable")
        .withProperty("spring.datasource.password","unit-fixture-placeholder")
        .withProperty("spring.security.oauth2.resourceserver.jwt.issuer-uri","https://identity.example.invalid")
        .withProperty("spring.security.oauth2.resourceserver.jwt.audiences","application")
        .withProperty("acp.runtime.timezone-artifact","2026d")
        .withProperty("acp.runtime.scheduler-profile","single-instance-postgresql-claims")
        .withProperty("acp.runtime.delivery","active")
        .withProperty("acp.runtime.deployment-profile","trusted-tls-proxy")
        .withProperty("server.forward-headers-strategy","framework")
        .withProperty("acp.runtime.trusted-proxy-network","true");}
    @Test void productionConfigurationFailsBeforeActivation() throws Exception {
        var model=new TargetModel();assertDoesNotThrow(()->RuntimeConfigurationContract.validate(production(),model,true));
        for(String key:new String[]{"acp.runtime.configuration-contract","acp.runtime.mode","spring.datasource.url","spring.datasource.username","spring.datasource.password","spring.security.oauth2.resourceserver.jwt.issuer-uri","spring.security.oauth2.resourceserver.jwt.audiences","acp.runtime.timezone-artifact","acp.runtime.scheduler-profile","acp.runtime.delivery","acp.runtime.deployment-profile","server.forward-headers-strategy","acp.runtime.trusted-proxy-network"}) {
            var env=production().withProperty(key,"");assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(env,model,true),key);
        }
        for(String[] bad:new String[][]{{"acp.runtime.configuration-contract","future"},{"acp.runtime.mode","test"},{"spring.datasource.url","jdbc:mysql://localhost/test"},{"spring.security.oauth2.resourceserver.jwt.issuer-uri","http://identity.example.invalid"},{"acp.runtime.timezone-artifact","system"},{"acp.runtime.scheduler-profile","unspecified"},{"acp.runtime.delivery","disabled"},{"acp.runtime.poll-enabled","false"},{"server.forward-headers-strategy","native"}}) {
            assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(production().withProperty(bad[0],bad[1]),model,true),bad[0]);
        }
    }
    @Test void activeDeliveryRequiresTransport() throws Exception {
        assertEquals("TRANSPORT_ADAPTER_REQUIRED",assertThrows(IllegalStateException.class,()->RuntimeConfigurationContract.validate(production(),new TargetModel(),false)).getMessage());
    }
}
