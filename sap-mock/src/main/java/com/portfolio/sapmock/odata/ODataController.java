package com.portfolio.sapmock.odata;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.portfolio.sapmock.repository.AbsenceRepository;
import com.portfolio.sapmock.repository.AppraisalRepository;
import com.portfolio.sapmock.repository.EmployeeRepository;
import com.portfolio.sapmock.repository.OvertimeRepository;
import com.portfolio.sapmock.repository.SalaryRepository;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;
import java.util.function.Supplier;

/**
 * SAP NetWeaver Gateway 의 OData v2 서비스를 재현한 컨트롤러.
 *
 * 실제 SAP 시스템의 URL 규칙을 그대로 따른다:
 *   /sap/opu/odata/sap/{서비스명}/{엔티티셋}?$filter=...&$top=...&$skip=...
 *
 * 지원 기능:
 *   - 서비스 문서(루트), $metadata (EDMX XML)
 *   - $filter(eq/ne/gt/ge/lt/le + and), $top, $skip, $inlinecount
 *   - 단건 조회: /EmployeeSet('10000001')
 *   - OData v2 JSON 응답 형식: {"d": {"results": [...]}}
 */
@RestController
@RequestMapping("/sap/opu/odata/sap/ZHR_EMP_SRV")
public class ODataController {

    private static final String SERVICE_NAMESPACE = "ZHR_EMP_SRV";

    private final Map<String, Supplier<List<?>>> entitySets = new LinkedHashMap<>();
    private final Map<String, String> entityTypeNames = new LinkedHashMap<>();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ODataController(EmployeeRepository employeeRepo, SalaryRepository salaryRepo,
                           OvertimeRepository overtimeRepo, AbsenceRepository absenceRepo,
                           AppraisalRepository appraisalRepo) {
        register("EmployeeSet", "Employee", employeeRepo::findAll);
        register("SalarySet", "Salary", salaryRepo::findAll);
        register("OvertimeSet", "Overtime", overtimeRepo::findAll);
        register("AbsenceSet", "Absence", absenceRepo::findAll);
        register("AppraisalSet", "Appraisal", appraisalRepo::findAll);
    }

    private void register(String setName, String typeName, Supplier<List<?>> source) {
        entitySets.put(setName, source);
        entityTypeNames.put(setName, typeName);
    }

    /** 서비스 문서: 이 서비스가 제공하는 엔티티셋 목록 */
    @GetMapping({"", "/"})
    public Map<String, Object> serviceDocument() {
        return Map.of("d", Map.of("EntitySets", new ArrayList<>(entitySets.keySet())));
    }

    /** $metadata: EDMX 스키마 문서 (SAP Gateway 클라이언트가 가장 먼저 요청하는 문서) */
    @GetMapping(value = "/$metadata", produces = MediaType.APPLICATION_XML_VALUE)
    public String metadata() throws IOException {
        return new ClassPathResource("odata-metadata.xml")
                .getContentAsString(StandardCharsets.UTF_8);
    }

    /** OData 단건 조회 구문: EmployeeSet('10000001') */
    private static final java.util.regex.Pattern KEY_ACCESS =
            java.util.regex.Pattern.compile("^(\\w+)\\('([^']+)'\\)$");

    /** 엔티티셋 조회 (컬렉션 또는 단건) */
    @GetMapping("/{entitySet}")
    public Map<String, Object> query(
            @PathVariable String entitySet,
            @RequestParam(name = "$filter", required = false) String filter,
            @RequestParam(name = "$top", required = false) Integer top,
            @RequestParam(name = "$skip", required = false, defaultValue = "0") int skip,
            @RequestParam(name = "$inlinecount", required = false) String inlineCount) {

        // 단건 조회: /EmployeeSet('10000001') 은 경로 패턴으로 분리되지 않으므로 직접 파싱
        java.util.regex.Matcher keyAccess = KEY_ACCESS.matcher(entitySet);
        if (keyAccess.matches()) {
            return byKey(keyAccess.group(1), keyAccess.group(2));
        }

        List<Map<String, Object>> rows = fetch(entitySet);

        if (filter != null && !filter.isBlank()) {
            Predicate<Map<String, Object>> predicate;
            try {
                predicate = ODataFilterParser.parse(filter);
            } catch (IllegalArgumentException e) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage());
            }
            rows = rows.stream().filter(predicate).toList();
        }

        int total = rows.size();
        rows = rows.stream().skip(skip).limit(top == null ? Long.MAX_VALUE : top).toList();

        Map<String, Object> d = new LinkedHashMap<>();
        if ("allpages".equals(inlineCount)) {
            d.put("__count", String.valueOf(total));
        }
        d.put("results", rows);
        return Map.of("d", d);
    }

    /** 단건 조회: /EmployeeSet('10000001') 형식 */
    private Map<String, Object> byKey(String entitySet, String key) {
        String keyField = "EmployeeSet".equals(entitySet) ? "Pernr" : "Id";
        return fetch(entitySet).stream()
                .filter(row -> key.equals(String.valueOf(row.get(keyField))))
                .findFirst()
                .map(row -> Map.<String, Object>of("d", row))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
                        entitySet + "('" + key + "') not found"));
    }

    /** 엔티티 → OData 응답용 맵 변환 (__metadata 포함) */
    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> fetch(String entitySet) {
        Supplier<List<?>> source = entitySets.get(entitySet);
        if (source == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,
                    "존재하지 않는 엔티티셋: " + entitySet + " (사용 가능: " + entitySets.keySet() + ")");
        }
        String type = SERVICE_NAMESPACE + "." + entityTypeNames.get(entitySet);
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Object entity : source.get()) {
            Map<String, Object> fields = objectMapper.convertValue(entity, LinkedHashMap.class);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("__metadata", Map.of("type", type));
            row.putAll(fields);
            rows.add(row);
        }
        return rows;
    }
}
