# COS 730 – Assignment 2: From Behavioural Models to Optimised Implementation

**Due date:** 14th May 2026 @ 11:00 am

---

## Overview

You are given a sequence diagram representing a subsystem of an **Intelligent Submission and Review System**. The sequence diagram models:

- Submitting an artefact
- Validating submission rules
- Assigning reviewers
- Performing evaluation checks
- Producing a final outcome

The provided design **intentionally includes**:
- Redundant interactions
- Poor responsibility allocation
- Inefficient decision handling
- Tight coupling between components

You are required to:
1. Implement the system as specified
2. Analyse inefficiencies in the design
3. Optimise the interaction model and decision logic
4. Re-implement the improved design
5. Empirically demonstrate performance and design improvements

---

## Tasks

### Task 1: Baseline Implementation (Correctness Phase) – [15 marks]

You must:
1. Implement the system **exactly** as specified in the provided sequence diagram
2. Ensure:
   - All interactions are preserved
   - Object responsibilities match the diagram
   - No optimisations are introduced at this stage

**Requirements:**
- Use an object-oriented language (e.g., Java, Python, C#)
- Maintain traceability between diagram elements and code

---

### Task 2: Design Analysis – [10 marks]

Critically evaluate the given design. Identify and explain:
- Redundant message calls
- Violations of good responsibility assignment
- High coupling / low cohesion areas
- Inefficient control flow
- Poor handling of decision logic

You must explicitly relate issues to:
- Responsibility assignment principles
- Behavioural modelling quality

---

### Task 3: Decision Modelling Using a Decision Table – [15 marks]

Extract all decision logic from the system and represent it using a **Decision Table**.

Your table must:
- Clearly define conditions and actions
- Eliminate ambiguity in decision-making
- Replace scattered conditional logic in the sequence diagram

You must also:
- Explain how the decision table improves clarity and maintainability
- Map decision table entries back to system behaviour

---

### Task 4: Sequence Diagram Optimisation – [10 marks]

Redesign the sequence diagram to:
- Reduce unnecessary interactions
- Improve responsibility allocation
- Decouple system components
- Centralise or properly distribute decision logic

Your optimised design must demonstrate:
- Improved cohesion
- Reduced coupling
- Cleaner control flow
- Better separation of concerns

---

### Task 5: Optimised Implementation – [20 marks]

Implement the improved sequence diagram.

You must:
- Refactor or redesign your initial implementation
- Align code with the optimised model
- Ensure functional equivalence with the original system

---

### Task 6: Empirical Evaluation and Comparison – [30 marks]

Compare the baseline vs optimised system using:

**Metrics (at minimum):**
- Number of method calls / interactions
- Execution time (benchmarking repeated runs)
- Code complexity (e.g., method size, class responsibilities)
- Maintainability indicators (qualitative + quantitative)

**Analysis must include:**
- Before vs after comparison
- Justification of improvements
- Trade-offs introduced by optimisation

---

## Deliverables

You must submit a **Technical PDF Report (15–20 pages)** that includes:
- Design analysis
- Identified issues
- Decision table construction
- Optimisation rationale
- Implementation discussion / screenshots
- Empirical evaluation and results

---

## Mark Allocation

| Task | Marks |
|------|-------|
| Task 1: Baseline Implementation | 15 |
| Task 2: Design Analysis | 10 |
| Task 3: Decision Table | 15 |
| Task 4: Sequence Diagram Optimisation | 10 |
| Task 5: Optimised Implementation | 20 |
| Task 6: Empirical Evaluation | 30 |
| **Total** | **100** |

---

> ⚠️ **ABSOLUTELY NO LATE SUBMISSIONS!**
