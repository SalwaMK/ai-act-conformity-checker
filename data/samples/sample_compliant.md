# TalentFilter AI v2.4 — System Specification, Risk Assessment & Compliance Documentation

**Document Control**  
*   **System Name:** TalentFilter AI (Enterprise Resume & Candidate Screening System)
*   **Version:** 2.4.0-prod
*   **Document Version:** 1.4
*   **Classification under EU AI Act:** High-Risk AI System (Annex III, Point 4(a) - Employment, workers management and access to self-employment)
*   **Author:** AI Governance & Safety Team, Voyverse Technologies Inc.
*   **Status:** Approved for Production Deployment

---

## 1. Intended Purpose & System Overview

### 1.1 Intended Purpose
TalentFilter AI is a machine learning-powered decision-support tool designed for enterprise HR departments. Its intended purpose is to assist human recruiters by ranking and shortlisting job applications for white-collar engineering, management, and administrative positions. The system processes resume PDFs, candidate cover letters, and structured application forms to produce suitability match scores (0–100) and structured skills summaries relative to standardized job descriptions.

### 1.2 Target User & Operational Environment
*   **Deployers:** Enterprise HR talent acquisition specialists and recruiting managers.
*   **Operational Context:** Cloud-hosted web platform integrated with standard Applicant Tracking Systems (ATS).
*   **Explicit Prohibitions & Out-of-Scope Use:**
    *   TalentFilter AI shall NOT be used as an automated decision-maker (i.e., automatic rejection of candidates without human review is strictly prohibited).
    *   The system is NOT intended or validated for evaluating blue-collar, manual labor, or executive C-suite roles without custom retraining.
    *   The system shall NOT process applications from candidates under 18 years of age without explicit manual routing.

---

## 2. Technical Architecture & Performance Specifications

### 2.1 Model Architecture & Data Lineage
*   **Core Model:** Fine-tuned Transformer-based NLP model with multi-task classification heads for skill extraction, experience duration estimation, and semantic role alignment.
*   **Training & Validation Datasets:** Trained on 450,000 anonymized historical application records spanning 2018–2025, balanced across regional labor markets within the EU and North America. All personally identifiable information (PII), gender indicators, age references, and address details were scrubbed prior to feature encoding.
*   **Validated Performance Metrics:**
    *   **Skill Extraction Precision:** 94.2% (±1.1% across demographic subgroups).
    *   **Role Suitability Ranking Accuracy (NDCG@10):** 0.89.
    *   **Robustness against Adversarial Formatting:** Tested against 1,000 adversarial resume layouts (e.g., hidden text, prompt injection attempts); system successfully flagged or stripped 98.4% of non-standard inputs.
    *   **Cybersecurity & Infrastructure:** Deployed on ISO 27001 and SOC 2 Type II certified cloud infrastructure with TLS 1.3 encryption in transit and AES-256 at rest.

---

## 3. Risk Management System (EU AI Act Article 9 Compliance)

### 3.1 Continuous Lifecycle Risk Management Process
The risk management system operates as a continuous, iterative lifecycle process integrated into Voyverse's CI/CD pipeline and quarterly compliance audits.

```
[ Risk Identification & Analysis ] ➔ [ Estimation & Evaluation ] ➔ [ Mitigation & Technical Control ] ➔ [ Residual Risk Acceptance ] ➔ [ Post-Market Monitoring Feedback Loop ]
```

### 3.2 Identified Risks & Hazard Analysis
1.  **Hazard R-01 (Algorithmic Bias & Discriminatory Impact):** Risk that historical hiring patterns skew scoring against protected classes, specific age groups (notably candidates over 50 or under 18), or non-native language speakers.
2.  **Hazard R-02 (Automation Bias & Human Over-reliance):** Risk that HR operators blindly accept high suitability scores without reviewing underlying candidate profiles or questioning anomalies.
3.  **Hazard R-03 (Adversarial Manipulation / Prompt Injection):** Candidates inserting invisible text or white-font keywords to trick the parser into assigning inflated scores.
4.  **Hazard R-04 (Concept Drift & Labor Market Shifts):** Emerging job titles or shifting skill terminologies causing degradation in ranking accuracy over time.

### 3.3 Mitigation Measures & Technical Controls
*   **Mitigation for R-01:** Demographic Parity & Disparate Impact Ratio (DIR) testing is conducted before every release. Sub-group performance parity is maintained within a 4/5ths rule threshold (DIR >= 0.82 across gender, age proxies, and nationality proxies). Age-impact analyses specifically evaluated performance for candidates under 18 and over 50.
*   **Mitigation for R-02:** Interface design requires HR specialists to view highlighted resume source text and write a brief justification before confirming candidate rejection or shortlisting.
*   **Mitigation for R-03:** Input sanitizer pipeline detects hidden layers, font size manipulation (<4pt), zero-width spaces, and prompt-injection keywords, routing flagged documents to raw text manual review.
*   **Mitigation for R-04:** Continuous Post-Market Monitoring System (per Article 72) ingests quarterly recruiter override logs and candidate feedback. Model drift triggers an automated re-validation alert if NDCG@10 drops below 0.85.

### 3.4 Residual Risk Assessment
Following the application of the above mitigations, all residual risks have been evaluated and judged to be acceptable by the Risk & Safety Board. The remaining residual risk of minor score variance is mitigated through the mandatory human oversight protocol (Section 5).

---

## 4. Transparency & Instructions for Deployers (EU AI Act Article 13 Compliance)

### 4.1 Instructions for Use
1.  **Deployment Setup:** Deployers must configure TalentFilter AI within their designated ATS using the provided API gateway.
2.  **Required Hardware & Computational Resources:**
    *   Client Requirement: Web browser (Chrome 110+, Firefox 115+, or Edge 110+) with minimum 1080p display resolution.
    *   API Latency Expectation: Average response time 450ms per resume; maximum batch throughput 500 documents per minute per tenant.
3.  **Maintenance & Software Updates:**
    *   Scheduled security patches: Bi-weekly on Sundays (no downtime).
    *   Major version updates: Semi-annually. Deployers will receive 30 days prior notice alongside updated model cards and change logs.

### 4.2 Interpretation of Outputs
*   **Score Definition:** The output score (0–100) represents statistical similarity to historical successful profiles for the given job description. It is NOT a measure of candidate intelligence, integrity, or guaranteed job performance.
*   **Explanatory Insights:** Every score is accompanied by feature attribution badges (e.g., "+15 pts: 5 years Python experience", "-10 pts: Missing required PMP certification").

### 4.3 Log Collection & Auditability Mechanisms (Article 12 Alignment)
*   The system automatically logs every API request, raw input hash, model version ID, candidate score, feature attributions, and deployer decision timestamp.
*   Logs are retained securely for 12 months in an immutable audit database, accessible via the Deployer Compliance Dashboard for regulatory inspections.

---

## 5. Human Oversight & Operational Controls (EU AI Act Article 14 Compliance)

### 5.1 Human-in-the-Loop Architecture
TalentFilter AI is strictly structured as a decision-support tool. The human-machine interface (HMI) enforces human oversight at two critical decision points:

1.  **Candidate Shortlisting:** No candidate is scheduled for an interview without explicit approval from a human recruiter.
2.  **Candidate Rejection:** Automatic rejection is disabled. Rejections require a two-click recruiter confirmation.

```
[ Application Submission ] ➔ [ TalentFilter AI Scoring ] ➔ [ HR Dashboard Display (Scores + Attributions) ] ➔ [ Human Recruiter Review & Verdict ] ➔ [ ATS Action ]
```

### 5.2 Specific Oversight Controls & UI Safety Features
*   **Dual-Human Verification for High-Impact Roles:** For senior or specialized roles, any decision to reject candidates falling within the 75th percentile score bracket requires confirmation by at least two natural persons (Recruitment Specialist + Hiring Manager).
*   **Override Capability:** HR operators can override any model score at any time with a single click. Overrides do not penalize operator workflow.
*   **Automation Bias Mitigation Warnings:** If an operator accepts 20 consecutive system recommendations without clicking to view candidate resumes, the UI triggers a mandatory 30-second pause with a warning pop-up: *"Please ensure thorough manual verification of resume details to maintain fair candidate evaluation."*
*   **Emergency Intervention & Safe-State Interrupt ("Stop Button"):**
    *   The Deployer Admin Panel includes a prominent red **"Suspend AI Screening"** button.
    *   Triggering this button immediately halts AI scoring across all active job postings, reverting the ATS workflow to traditional manual resume sorting in a verified safe state without data loss.

---

## 6. Pre-Market Validation & Testing Summary
*   **Test Environment:** Real-world shadow testing conducted across 25,000 historical applications across 3 EU enterprise partners between Oct 2025 and Jan 2026.
*   **Results:** System maintained 99.2% uptime, zero unauthorized data disclosures, and zero recorded instances of adverse disparate impact exceeding legal thresholds.
