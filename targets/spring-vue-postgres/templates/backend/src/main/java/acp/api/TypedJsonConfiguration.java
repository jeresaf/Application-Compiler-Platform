package acp.api;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** Explicit converter matches the generated typed readers; never silently use another codec. */
@Configuration
public class TypedJsonConfiguration implements WebMvcConfigurer {
    public static ObjectMapper mapper() {
        return new ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
            .enable(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES)
            .enable(DeserializationFeature.FAIL_ON_MISSING_CREATOR_PROPERTIES);
    }
    @Override public void extendMessageConverters(List<HttpMessageConverter<?>> converters) {
        converters.removeIf(c -> c.getClass().getSimpleName().contains("Jackson"));
        converters.addFirst(new MappingJackson2HttpMessageConverter(mapper()));
    }
}
