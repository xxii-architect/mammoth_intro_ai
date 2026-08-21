# MammothOS Package Offering

MammothOS can now be described as a productized Python package instead of a repo-only prototype.

## Positioning

**MammothOS package**
- the installable runtime and SDK surface
- suitable for internal operator tools, prototypes, and embed integrations

**ATLAS FAB**
- the learner-facing embed story on top of the package
- best framed as the commercial wedge for tutoring and enablement use cases

## Package architecture

```mermaid
flowchart TD
    Install[pip install mammoth-os] --> SDK[Public SDK surface]
    Install --> CLI[CLI entry point]
    InstallServer[pip install mammoth-os[server]] --> API[FastAPI backend]
    SDK --> Session[ATLASSession compatibility]
    SDK --> FAB[AtlasFAB contract]
    API --> UI[Command Center UI]
    API --> Auth[Tenant / auth guardrails]
```

## Packaging tiers

| Offer | Install | Audience | Notes |
|---|---|---|---|
| Base SDK | `pip install mammoth-os` | embedders, local operators | smallest install, core runtime + SDK |
| Server stack | `pip install mammoth-os[server]` | backend operators | adds FastAPI + uvicorn for hosted flows |
| Future enterprise distribution | private package / hosted API | commercial customers | should include tenant auth, billing, support, and docs portal |

## Pricing skeleton

| Layer | Draft commercial posture | What it should include |
|---|---|---|
| Open package | free / developer entry | install docs, examples, stable imports |
| Hosted Pro | monthly workspace plan | tenant auth, usage warnings, export tooling, support response targets |
| Enterprise | custom contract | onboarding, white-label, governance, rollout planning |

## Sales-facing summary

If someone asks why they should buy or adopt this package, the answer is:

1. it gives them a real SDK contract instead of a loose prompt recipe
2. it preserves compatibility with legacy `ATLASSession` flows
3. it creates a path from local prototype to tenant-aware hosted product
4. it keeps runtime-state and fallback behavior inspectable instead of hidden

## Recommended collateral to build next

- integration recipes for FastAPI, React, and internal tools
- a hosted quickstart with tenant bootstrap
- a billing / entitlements explainer tied to real backend endpoints
- comparison copy: generic chatbot embed vs ATLAS FAB guided-learning embed
