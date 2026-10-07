package acp.api;

import acp.application.TaskService;
import acp.infrastructure.TargetModel;
import java.util.List;
import java.util.Map;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class TaskController {
    private final TargetModel model;
    private final TaskService tasks;
    public TaskController(TargetModel model, TaskService tasks) { this.model = model; this.tasks = tasks; }
    public record TaskRequest(String resourceId, long expectedVersion, Map<String, Object> input) {}

    private String resolve(String key, String method) {
        for (var operation : model.model.path("api")) {
            if (operation.path("path").asText().equals("/api/" + key) && operation.path("method").asText().equals(method)) return operation.path("origin").path("id").asText();
        }
        throw new IllegalArgumentException("UNKNOWN_OPERATION");
    }

    @PostMapping("/{key}")
    public Map<String, Object> execute(@PathVariable String key, @RequestBody TaskRequest request, @AuthenticationPrincipal Jwt identity) {
        if (request.resourceId() == null || request.input() == null) throw new IllegalArgumentException("REQUEST");
        return tasks.execute(resolve(key, "POST"), request.resourceId(), request.expectedVersion(), request.input(), identity);
    }

    @GetMapping("/{key}")
    public List<Map<String, Object>> query(@PathVariable String key, @RequestParam(defaultValue="0") int offset,
        @RequestParam(defaultValue="25") int limit, @RequestParam(defaultValue="") String search, @AuthenticationPrincipal Jwt identity) {
        return tasks.query(resolve(key, "GET"), offset, limit, search, identity);
    }
}
