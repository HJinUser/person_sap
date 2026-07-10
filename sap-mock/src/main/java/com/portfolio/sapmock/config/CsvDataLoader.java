package com.portfolio.sapmock.config;

import com.portfolio.sapmock.entity.Absence;
import com.portfolio.sapmock.entity.Appraisal;
import com.portfolio.sapmock.entity.Employee;
import com.portfolio.sapmock.entity.OvertimeRecord;
import com.portfolio.sapmock.entity.SalaryRecord;
import com.portfolio.sapmock.repository.AbsenceRepository;
import com.portfolio.sapmock.repository.AppraisalRepository;
import com.portfolio.sapmock.repository.EmployeeRepository;
import com.portfolio.sapmock.repository.OvertimeRepository;
import com.portfolio.sapmock.repository.SalaryRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 기동 시 data/ 폴더의 CSV를 읽어 H2 인메모리 DB에 적재한다.
 * 실제 SAP이라면 이 데이터가 ERP 트랜잭션으로 쌓여 있을 것이고,
 * 이 프로젝트에서는 합성 데이터 생성기(data-gen)가 그 역할을 대신한다.
 */
@Component
public class CsvDataLoader implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(CsvDataLoader.class);

    private final EmployeeRepository employeeRepo;
    private final SalaryRepository salaryRepo;
    private final OvertimeRepository overtimeRepo;
    private final AbsenceRepository absenceRepo;
    private final AppraisalRepository appraisalRepo;

    @Value("${hr.data-dir}")
    private String dataDir;

    public CsvDataLoader(EmployeeRepository employeeRepo, SalaryRepository salaryRepo,
                         OvertimeRepository overtimeRepo, AbsenceRepository absenceRepo,
                         AppraisalRepository appraisalRepo) {
        this.employeeRepo = employeeRepo;
        this.salaryRepo = salaryRepo;
        this.overtimeRepo = overtimeRepo;
        this.absenceRepo = absenceRepo;
        this.appraisalRepo = appraisalRepo;
    }

    @Override
    public void run(String... args) throws Exception {
        Path dir = Path.of(dataDir);
        if (!Files.exists(dir)) {
            log.warn("데이터 폴더가 없습니다: {} — data-gen/generate.py를 먼저 실행하세요.", dir.toAbsolutePath());
            return;
        }
        employeeRepo.saveAll(load(dir.resolve("employees.csv"), Employee::new));
        salaryRepo.saveAll(load(dir.resolve("salary_history.csv"), SalaryRecord::new));
        overtimeRepo.saveAll(load(dir.resolve("overtime.csv"), OvertimeRecord::new));
        absenceRepo.saveAll(load(dir.resolve("absences.csv"), Absence::new));
        appraisalRepo.saveAll(load(dir.resolve("appraisals.csv"), Appraisal::new));
        log.info("CSV 적재 완료 — 사원 {}건, 급여 {}건, 초과근무 {}건, 근태 {}건, 평가 {}건",
                employeeRepo.count(), salaryRepo.count(), overtimeRepo.count(),
                absenceRepo.count(), appraisalRepo.count());
    }

    private <T> List<T> load(Path file, Function<String[], T> mapper) throws Exception {
        try (BufferedReader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
            return reader.lines()
                    .skip(1) // 헤더
                    .filter(line -> !line.isBlank())
                    .map(line -> mapper.apply(line.split(",", -1)))
                    .collect(Collectors.toList());
        }
    }
}
