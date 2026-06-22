package com.example.medical.repository;

import com.example.medical.dto.PatientListItem;
import com.example.medical.model.Patient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.List;

@Repository
public class PatientRepository {

    private final JdbcTemplate jdbcTemplate;

    public PatientRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<Patient> findAll() {
        String sql = """
                SELECT id,name,gender,age,created_at,updated_at
                FROM patients
                ORDER BY id DESC
                """;
        return jdbcTemplate.query(sql, (rs, rowNum) -> {
            Patient patient = new Patient();
            patient.setId(rs.getLong("id"));
            patient.setName(rs.getString("name"));
            patient.setGender(rs.getString("gender"));
            patient.setAge(rs.getInt("age"));
            patient.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            patient.setUpdatedAt(rs.getTimestamp("updated_at").toLocalDateTime());
            return patient;
        });
    }

    public Patient findById(Long id) {
        String sql = """
                SELECT id, name ,gender,age,created_at,updated_at
                FROM patients
                WHERE id = ?
                """;

        return jdbcTemplate.queryForObject(sql, (rs, rowNum) -> {
            Patient patient = new Patient();
            patient.setId(rs.getLong("id"));
            patient.setName(rs.getString("name"));
            patient.setGender(rs.getString("gender"));
            patient.setAge(rs.getInt("age"));
            patient.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            patient.setUpdatedAt(rs.getTimestamp("updated_at").toLocalDateTime());
            return patient;
        }, id);
    }

    public int create(String name, String gender, Integer age) {
        String sql = """
                INSERT INTO patients (name,gender,age)
                VALUES (?,?,?)
                """;
        return jdbcTemplate.update(sql, name, gender, age);
    }

    public int update(Long id, String name, String gender, Integer age) {
        String sql = """
                UPDATE patients SET name =? , gender= ? , age =  ?
                WHERE id = ?
                """;
        return jdbcTemplate.update(sql, name, gender, age, id);
    }

    @Transactional
    public int deleteById(Long id) {
        jdbcTemplate.update("DELETE FROM test_records WHERE patient_id = ?", id);

        String sql = """
                DELETE FROM patients
                WHERE id = ?
                """;
        return jdbcTemplate.update(sql, id);
    }

    public List<Patient> search(String keyword, String gender, String sortBy, String order) {
        StringBuilder sql = new StringBuilder("""

                SELECT id,name,gender,age,created_at,updated_at
                FROM patients
                WHERE 1=1
                    """);
        List<Object> params = new ArrayList<>();
        if (keyword != null && !keyword.isBlank()) {
            sql.append(" AND name LIKE ?");
            params.add("%" + keyword + "%");
        }
        if (gender != null && !gender.isBlank()) {
            sql.append(" AND gender = ?");
            params.add(gender);
        }
        String sortColumn = resolveSortColumn(sortBy);
        String sortOrder = resolveSortOrder(order);
        sql.append(" ORDER BY ").append(sortColumn).append(" ").append(sortOrder);
        return jdbcTemplate.query(sql.toString(), (rs, rowNum) -> {
            Patient patient = new Patient();
            patient.setId(rs.getLong("id"));
            patient.setName(rs.getString("name"));
            patient.setGender(rs.getString("gender"));
            patient.setAge(rs.getInt("age"));
            patient.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            patient.setUpdatedAt(rs.getTimestamp("updated_at").toLocalDateTime());
            return patient;
        }, params.toArray());
    }

    public List<PatientListItem> searchWithLatestRecord(
            String keyword,
            String gender,
            String result,
            String sortBy,
            String order) {
        StringBuilder sql = new StringBuilder("""
                SELECT
                    p.id,
                    p.name,
                    p.gender,
                    p.age,
                    p.created_at,
                    p.updated_at,
                    latest.result AS latest_result,
                    latest.confidence AS latest_confidence,
                    latest.tested_at AS latest_tested_at
                FROM patients p
                LEFT JOIN test_records latest
                    ON latest.id = (
                        SELECT tr.id
                        FROM test_records tr
                        WHERE tr.patient_id = p.id
                        ORDER BY tr.tested_at DESC, tr.id DESC
                        LIMIT 1
                    )
                WHERE 1 = 1
                """);

        List<Object> params = new ArrayList<>();

        if (keyword != null && !keyword.isBlank()) {
            sql.append(" AND p.name LIKE ?");
            params.add("%" + keyword + "%");
        }

        if (gender != null && !gender.isBlank()) {
            sql.append(" AND p.gender = ?");
            params.add(gender);
        }

        if ("NO_RECORD".equals(result)) {
            sql.append(" AND latest.id IS NULL");
        } else if (result != null && !result.isBlank()) {
            sql.append(" AND latest.result = ?");
            params.add(result);
        }

        String sortColumn = resolvePatientListSortColumn(sortBy);
        String sortOrder = resolveSortOrder(order);
        sql.append(" ORDER BY ").append(sortColumn).append(" ").append(sortOrder);

        return jdbcTemplate.query(sql.toString(), (rs, rowNum) -> {
            PatientListItem item = new PatientListItem();

            item.setId(rs.getLong("id"));
            item.setName(rs.getString("name"));
            item.setGender(rs.getString("gender"));
            item.setAge(rs.getInt("age"));
            item.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
            item.setUpdatedAt(rs.getTimestamp("updated_at").toLocalDateTime());
            item.setLatestResult(rs.getString("latest_result"));
            item.setLatestConfidence(rs.getBigDecimal("latest_confidence"));

            Timestamp latestTestedAt = rs.getTimestamp("latest_tested_at");
            if (latestTestedAt != null) {
                item.setLatestTestedAt(latestTestedAt.toLocalDateTime());
            }

            return item;
        }, params.toArray());
    }

    private String resolvePatientListSortColumn(String sortBy) {
        if (sortBy == null || sortBy.isBlank()) {
            return "p.id";
        }

        return switch (sortBy) {
            case "id" -> "p.id";
            case "name" -> "p.name";
            case "gender" -> "p.gender";
            case "age" -> "p.age";
            case "createdAt" -> "p.created_at";
            case "updatedAt" -> "p.updated_at";
            case "latestResult" -> "latest_result";
            case "latestConfidence" -> "latest_confidence";
            case "latestTestedAt" -> "latest_tested_at";
            default -> "p.id";
        };
    }

    private String resolveSortColumn(String sortBy) {
        if (sortBy == null || sortBy.isBlank()) {
            return "id  ";
        }
        return switch (sortBy) {
            case "id" -> "id";
            case "name" -> "name";
            case "gender" -> "gender";
            case "age" -> "age";
            case "createdAt" -> "created_at";
            case "updatedAt" -> "updated_at";
            default -> "id";
        };
    }

    private String resolveSortOrder(String order) {
        if ("asc".equalsIgnoreCase(order)) {
            return "ASC";
        }
        return "DESC";
    }
}
