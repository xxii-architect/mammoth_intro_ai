# MammothOS Product Landing — Quick Reference Guide

**Purpose:** Single-source reference for all product positioning, CTAs, and documentation links.

---

## Product Summary (30 seconds)

### ATLAS FAB — "Tutoring Precision. Every Learner."
**For:** EdTech builders, training teams, product managers  
**What:** Embeddable adaptive tutoring SDK + runtime visibility  
**Why:** Page-aware coaching that stays synchronized with learner workflow  
**Hero CTA:** "Explore ATLAS FAB"

### MammothOS SDK — "Orchestrate. Reason. Scale."
**For:** AI engineers, platform architects, developers  
**What:** Multi-agent orchestration Python package with recursive reasoning  
**Why:** Production-grade SDK contract with safety gates and observability  
**Hero CTA:** "Get Started with MammothOS"

### Learning Platform — "Knowledge That Adapts. Learners That Grow."
**For:** Schools, corporates, field operations  
**What:** Adaptive curriculum engine + learner experience + operator analytics  
**Why:** Tailored learning that grows real skill without static cohorts  
**Hero CTA:** "Launch a Learning Experience"

---

## CTA Architecture

### Navigation Flow

```
truexxiisupply.com (Marketing)
├─ Hero section: 3 product pills/links
├─ #atlas-fab-product section (on page)
│  └─ CTA: "Explore ATLAS FAB" → command.truexxiisupply.com/atlas-fab
│
├─ #mammoth-os-sdk section (on page)
│  └─ CTA: "Get Started with MammothOS" → pypi.org/project/mammoth-os
│
└─ #learning-platform section (on page)
   └─ CTA: "Launch a Learning Experience" → command.truexxiisupply.com/learning-platform-demo

command.truexxiisupply.com (Operations)
├─ /atlas-fab (Product landing page)
│  ├─ Primary: "Explore ATLAS FAB"
│  ├─ Secondary: "View Technical Docs"
│  └─ Tertiary: "See SDK on PyPI"
│
├─ /sdk-quickstart (SDK onboarding)
│  ├─ Primary: "Get Started with MammothOS"
│  ├─ Secondary: "Read the Architecture Guide"
│  └─ Tertiary: "View on GitHub"
│
├─ /learning-platform-demo (Learning platform demo)
│  ├─ Primary: "Launch a Learning Experience"
│  ├─ Secondary: "Explore Curriculum Guides"
│  └─ Tertiary: "Request an Enterprise Demo"
│
└─ Footer: "← Back to Marketing Site" → truexxiisupply.com
```

---

## CTA Link Reference

### ATLAS FAB
| CTA Label | Link | Type | Purpose |
|---|---|---|---|
| **Explore ATLAS FAB** | `/atlas-fab` | Internal | Product landing page |
| View Technical Docs | `https://github.com/xxii-architect/mammoth_intro_ai/blob/main/docs/atlas_fab_product_guide.md` | External | ATLAS FAB Product Guide |
| See SDK on PyPI | `https://pypi.org/project/mammoth-os/` | External | PyPI package page |

### MammothOS SDK
| CTA Label | Link | Type | Purpose |
|---|---|---|---|
| **Get Started with MammothOS** | `https://pypi.org/project/mammoth-os/` | External | PyPI install page |
| Read the Architecture Guide | `https://github.com/xxii-architect/mammoth_intro_ai/blob/main/docs/mammoth_os_package_offering.md` | External | Package offering doc |
| View on GitHub | `https://github.com/xxii-architect/mammoth_intro_ai` | External | Repository root |

### Learning Platform
| CTA Label | Link | Type | Purpose |
|---|---|---|---|
| **Launch a Learning Experience** | `/learning-platform-demo` or `/` (depending on implementation) | Internal | Platform demo or app |
| Explore Curriculum Guides | `https://github.com/xxii-architect/mammoth_intro_ai/blob/main/ATLAS_MANUAL.md` | External | ATLAS Manual |
| Request an Enterprise Demo | `/contact?product=learning-platform` | Internal | Contact form (product-scoped) |

---

## Brand Voice Checklist

### Tone Rules
- ✅ Sophisticated, precise, operator-focused
- ✅ Specific capabilities (not generic buzzwords)
- ✅ Measurable outcomes, technical credibility
- ✅ Language patterns:
  - "Adaptive" not "smart"
  - "Operator visibility" not "dashboards"
  - "Structured flows" not "powerful AI"
  - "Production-grade" not "enterprise-ready"
  - "Failure modes" not "error handling"

### Color Usage
- **Primary CTA:** Ember (#c0392b) gradient to Amber (#e67e22)
- **Secondary CTA:** Ember border, transparent bg, hover opacity increase
- **Callout boxes:** Base-lighter (#1a1a1a) bg + Ember/Amber borders
- **Feature cards:** Base-light (#111111) bg, hover lift effect
- **Text:** White (#ffffff) headings, Secondary gray (#cccccc) body

### Contrast & Accessibility
- All body copy: 4.5:1 minimum contrast ratio
- CTAs: High contrast on dark bg (white on ember/amber)
- Borders: Use opacity (0.2–0.3) for subtle separation

---

## Product Comparison Matrix

| Aspect | ATLAS FAB | SDK | Learning Platform |
|---|---|---|---|
| **Audience** | EdTech, trainers | Engineers, architects | Schools, corporates |
| **Format** | Python SDK | Python package | Full app + backend |
| **Integration** | Embed in existing app | Import + orchestrate | Standalone or embed |
| **Deployment** | Local or hosted | Local, FastAPI, or tenant | Hosted dashboard + API |
| **Pricing Model** | Per-app / per-deployment | Per-workspace | Per-learner |
| **Primary Value** | Adaptive tutoring | Multi-agent orchestration | Personalized learning |
| **Key Feature** | Page-aware context | Recursive reasoning | Adaptive curriculum |

---

## Landing Page Sections (In Order)

1. **Hero** (All products)
   - Headline: "Adaptive learning infrastructure for teams, learners, and builders."
   - Subheading: "MammothOS connects the learning platform, the ATLAS FAB embed, and the Python SDK..."
   - CTAs: "Open Learning Platform", "Explore ATLAS FAB"

2. **Product Offers Section** (Grid of 3 cards)
   - Card 1: ATLAS FAB with eyebrow, headline, bullets, primary/secondary actions
   - Card 2: MammothOS SDK with eyebrow, headline, bullets, primary/secondary actions
   - Card 3: Learning Platform with eyebrow, headline, bullets, primary/secondary actions

3. **Workflow Steps** (Existing)
   - Showcasing multi-step learning, execution, collaboration flows

4. **Footer Navigation** (Cross-linking)
   - "Part of the MammothOS Platform Ecosystem"
   - Links: "← Back to Marketing Site" | "GitHub Repository" | "Contact Sales"

---

## Implementation Checklist

### Content Finalization
- [x] Hero headlines (all 3 products)
- [x] Body copy (300+ words per product)
- [x] Feature grids and differentiators
- [x] Use case cards (3 per product)
- [x] CTA labels and doc links
- [x] Brand guidelines

### HTML / Frontend
- [x] Tailwind-based responsive templates
- [x] Color scheme: Ember, Amber, Base colors
- [x] Hover states for cards and CTAs
- [x] Mobile-first layout

### Backend (To Do)
- [ ] Wire `/atlas-fab` endpoint
- [ ] Wire `/sdk-quickstart` endpoint
- [ ] Wire `/learning-platform-demo` endpoint
- [ ] Wire `/contact?product=X` form handler

### Integration (To Do)
- [ ] Update truexxiisupply.com with product sections
- [ ] Add cross-links on marketing site
- [ ] Add cross-links on command center
- [ ] Test all CTAs and doc links

### Analytics (To Do)
- [ ] Set up event tracking for CTAs
- [ ] Track docs opened
- [ ] Track form submissions
- [ ] Monitor early engagement

---

## Example Use Cases

### ATLAS FAB — Use in EdTech Platform
1. User visits product page: `/atlas-fab`
2. Reads luxury copy on adaptive tutoring + page-aware coaching
3. Clicks "View Technical Docs" → GitHub guide
4. Clicks "See SDK on PyPI" → PyPI page to install
5. Follows quickstart in docs
6. Embeds SDK into their app

### SDK — Use for AI Engineers
1. User visits `/sdk-quickstart`
2. Sees code example of MammothOS orchestration
3. Clicks "Get Started with MammothOS" → PyPI
4. Runs `pip install mammoth-os`
5. Clicks "Read Architecture Guide" → GitHub docs
6. Integrates into their project

### Learning Platform — Use for School District
1. User visits `/learning-platform-demo`
2. Reads about adaptive curriculum + operator analytics
3. Clicks "Launch a Learning Experience" → app demo
4. Explores curriculum builder UI
5. Clicks "Request an Enterprise Demo" → contact form
6. Sales team follows up with demo + custom onboarding

---

## Frequently Asked Questions (For Copy Review)

**Q: Is the tone too promotional?**  
**A:** No. Copy focuses on specific capabilities (adaptive context, structured flows, operator visibility) rather than hype. Tone is sophisticated + technical.

**Q: Should we include pricing?**  
**A:** Pricing is skeleton only (Explorer/Pro/Enterprise tiers). Full checkout wired later. Current copy mentions pricing to set expectations.

**Q: How do we position the products without cannabilizing each other?**  
**A:** Each solves a different buyer's need: ATLAS = product teams, SDK = engineers, Platform = operators/schools. No direct competition; complementary.

**Q: Should we split into separate landing pages?**  
**A:** No. Unified MammothOS story with three product entry points. Users can understand the whole ecosystem from one page.

**Q: What if a doc link goes down?**  
**A:** Add version-controlled backup copies on command center `/docs/` routes. Ensure GitHub links point to stable branches (main or release tags).

---

## Deployment Readiness

| Component | Status | Notes |
|---|---|---|
| Copy (all 3 products) | ✅ READY | Finalized, brand-compliant, proofread |
| HTML templates | ✅ READY | Tailwind-based, responsive, color-coded |
| Integration strategy | ✅ READY | Roadmap + technical requirements documented |
| Backend routes | ⏳ TODO | FastAPI endpoints need wiring |
| Frontend integration | ⏳ TODO | Cross-links need wiring on both domains |
| Analytics setup | ⏳ TODO | Event tracking + conversion metrics |

**Go-live readiness:** Content is 100% ready. Backend/frontend integration needed before production deployment.

---

## Support & Refinement

- **Copy questions:** See `docs/product_landing_copy.md` for full copy, brand guidelines, positioning details
- **Technical questions:** See `docs/LANDING_PAGE_STRATEGY.md` for implementation roadmap and backend requirements
- **HTML questions:** See `docs/product_landing_sections.html` for reusable Tailwind components
- **FrontEnd questions:** See `ui/mad-architekt-command-center/src/pages/LandingPage.jsx` for current implementation

---

**Last updated:** Current session  
**Commit:** 7357884  
**Status:** ✅ Content Complete, Awaiting Backend Integration
