package com.example.medical.controller;

import com.example.medical.dto.CreateOperationLogRequest;
import com.example.medical.model.OperationLog;
import com.example.medical.repository.OperationLogRepository;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
public class OperationLogController {
    private final OperationLogRepository operationLogRepository;

    public OperationLogController(OperationLogRepository operationLogRepository) {
        this.operationLogRepository = operationLogRepository;
    }

    @GetMapping("/api/operation-logs")
    public Map<String, Object> listOperationLogs() {
        List<OperationLog> logs = operationLogRepository.findAll();
        return Map.of("code", 0, "message", "success", "data", logs);
    }

    @PostMapping("/api/operation-logs")
    public Map<String, Object> createOperationLog(@RequestBody CreateOperationLogRequest request) {
        int affectedRows = operationLogRepository.create(request.getAction(), request.getDetail());
        return Map.of("code", 0, "message", "success", "data", Map.of("affectedRows", affectedRows));
    }

    @DeleteMapping("/api/operation-logs/{id}")
    public Map<String, Object> deleteOperationLog(@PathVariable Long id) {
        int affectedRows = operationLogRepository.deleteById(id);
        return Map.of("code", 0, "message", "success", "data", Map.of("affectedRows", affectedRows));
    }

    @DeleteMapping("/api/operation-logs")
    public Map<String, Object> clearOperationLogs() {
        int affectedRows = operationLogRepository.deleteAll();
        return Map.of("code", 0, "message", "success", "data", Map.of("affectedRows", affectedRows));
    }
}
