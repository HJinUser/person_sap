package com.portfolio.sapmock.repository;

import com.portfolio.sapmock.entity.OvertimeRecord;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OvertimeRepository extends JpaRepository<OvertimeRecord, Long> {
}
