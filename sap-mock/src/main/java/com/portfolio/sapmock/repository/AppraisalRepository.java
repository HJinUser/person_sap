package com.portfolio.sapmock.repository;

import com.portfolio.sapmock.entity.Appraisal;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AppraisalRepository extends JpaRepository<Appraisal, Long> {
}
