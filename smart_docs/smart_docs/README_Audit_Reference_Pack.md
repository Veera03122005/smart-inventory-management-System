# SmartStock AI — Audit Reference Pack

Place this entire `smart_docs` folder in the root of the SmartStock AI repository before running the independent audit.

## Contents

1. `SmartStock_AI_Complete_Project_Concept.md` — complete V1 project concept.
2. `SmartStock_AI_Design_Specification.md` — architecture and design specification.
3. `README_SmartStock_AI.md` — project README/product context.
4. `V1_Research_and_Implementation_Spec.md` — earlier V1 research and implementation specification.
5. `Approved_Owner_Manager_Staff_Workflows.md` — consolidated approved role workflows and accounting rules.
6. `Phase_1_to_3_Implementation_Requirements.md` — phase acceptance criteria and cross-phase invariants.

## Source precedence

The documents were created at different stages and may describe different scope levels. For the V1 audit:
- Use the Complete Project Concept and approved workflow document as the latest V1 product/workflow authority.
- Use the Design Specification for architecture, data, security and engineering constraints.
- Use the Phase 1–3 requirements for phase acceptance.
- Use the README for broader project context, but do not pull future roadmap features into V1.
- Treat the older V1 Research and Implementation Specification as historical context where it conflicts with the later finalized V1 scope.

## Important

This folder contains specifications and acceptance criteria. It does not prove that the source repository implements them. The audit must inspect actual source code, migrations, tests and Git state.

Phase 1, Phase 2, Phase 2.1 and Phase 3 completion reports supplied earlier are implementation claims to verify, not substitutes for this specification pack.
