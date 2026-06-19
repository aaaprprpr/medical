package com.example.medical.repository;

import com.example.medical.model.Patient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

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

}
