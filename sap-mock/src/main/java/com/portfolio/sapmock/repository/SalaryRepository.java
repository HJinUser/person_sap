package com.portfolio.sapmock.repository;

import com.portfolio.sapmock.entity.SalaryRecord;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SalaryRepository extends JpaRepository<SalaryRecord, Long> {
}
