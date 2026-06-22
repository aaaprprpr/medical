package com.example.medical.repository;

import com.example.medical.model.OperationLog;
import jakarta.annotation.PostConstruct;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class OperationLogRepository {
    private final JdbcTemplate jdbcTemplate;

    public OperationLogRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @PostConstruct
    public void initTable() {
        String sql = """
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    action VARCHAR(100) NOT NULL,
                    detail VARCHAR(500),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """;
        jdbcTemplate.execute(sql);
    }

    public List<OperationLog> findAll() {
        String sql = """
                SELECT id, action, detail, created_at
                FROM operation_logs
                ORDER BY created_at DESC, id DESC
                """;
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            OperationLog log = new OperationLog();
            log.setId(rs.getLong("id"));
            log.setAction(rs.getString("action"));
            log.setDetail(rs.getString("detail"));
            log.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            return log;
        });
    }

    public int create(String action, String detail) {
        String sql = """
                INSERT INTO operation_logs(action, detail)
                VALUES (?, ?)
                """;
        return jdbcTemplate.update(sql, action, detail);
    }

    public int deleteById(Long id) {
        String sql = """
                DELETE FROM operation_logs
                WHERE id = ?
                """;
        return jdbcTemplate.update(sql, id);
    }

    public int deleteAll() {
        return jdbcTemplate.update("DELETE FROM operation_logs");
    }
}
