package com.example.medical.repository;

import com.example.medical.model.TestRecord;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.util.List;

@Repository
public class TestRecordRepository {
    private final JdbcTemplate jdbcTemplate;

    public TestRecordRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<TestRecord> findByPatientId(Long patientId) {
        String sql = """
                SELECT id ,patient_id,result,confidence ,tested_at,remark
                FROM test_records
                WHERE PATIENT_ID = ?
                ORDER BY tested_at DESC
                """;
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            TestRecord record = new TestRecord();
            record.setId(rs.getLong("id"));
            record.setPatientId(rs.getLong("patient_id"));
            record.setResult(rs.getString("result"));
            record.setConfidence(rs.getBigDecimal("confidence"));
            record.setTestedAt(rs.getTimestamp("tested_at").toLocalDateTime());
            record.setRemark(rs.getString("remark"));
            return record;
        }, patientId);
    }

    public int create(Long patientId, String result, BigDecimal confidence, String remark) {
        String sql = """
                INSERT INTO test_records(patient_id,result,confidence,remark)
                VALUES (?,?,?,?)
                """;
        return jdbcTemplate.update(sql, patientId, result, confidence, remark);
    }
}
