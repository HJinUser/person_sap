package com.portfolio.sapmock.repository;

import com.portfolio.sapmock.entity.Employee;
import org.springframework.data.jpa.repository.JpaRepository;

public interface EmployeeRepository extends JpaRepository<Employee, String> {
}
