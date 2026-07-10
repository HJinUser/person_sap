package com.portfolio.sapmock.repository;

import com.portfolio.sapmock.entity.Absence;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AbsenceRepository extends JpaRepository<Absence, Long> {
}
