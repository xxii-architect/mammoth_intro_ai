# Landing Page Integration & Cross-Linking Strategy

> **Executive Summary:** Three luxury-positioned product landing copy blocks (ATLAS FAB, MammothOS SDK, Learning Platform) with HTML templates, CTA labels, doc links, and cross-linking architecture between truexxiisupply.com and command.truexxiisupply.com.

---

## Overview

The MammothOS ecosystem now has three distinct products, each with its own buyer persona, value proposition, and conversion intent. This guide ensures they're positioned consistently across marketing and operational domains while maintaining luxury brand voice and precise technical credibility.

### Products & Buyers

| Product | Primary Buyer | Primary Value | URL |
|---|---|---|---|
| **ATLAS FAB** | EdTech builders, training teams, product managers | Embeddable adaptive tutoring + cost control | `/atlas-fab` |
| **MammothOS SDK** | Developers, AI engineers, platform teams | Multi-agent orchestration + safety + observability | `/sdk-quickstart` |
| **Learning Platform** | Schools, enterprises, operators | Adaptive curriculum + field-ready deployment + learner insights | `/learning-platform-demo` |

---

## Implementation Roadmap

### Phase 1: Finalize Copy & Brand Alignment (✅ COMPLETE)
- [x] Draft hero headlines for each product (luxury tone)
- [x] Draft luxury body copy blocks (300–400 words each)
- [x] Create feature grids and differentiators
- [x] Define CTA labels and doc link URIs
- [x] Create HTML template with Tailwind integration

**Artifacts:**
- `docs/product_landing_copy.md` — All copy, brand guidelines, positioning
- `docs/product_landing_sections.html` — Reusable HTML components

### Phase 2: Backend Integration (NEXT)
- [ ] Wire `/atlas-fab` endpoint on command center (FastAPI)
- [ ] Wire `/sdk-quickstart` endpoint (with embedded code examples)
- [ ] Wire `/learning-platform-demo` endpoint (with curriculum builder preview)
- [ ] Add `/contact?product=X` form handler for lead capture

### Phase 3: Frontend Integration (SECONDARY)
- [ ] Update truexxiisupply.com landing page with cross-links to each product section
- [ ] Add product navigation menu on command.truexxiisupply.com
- [ ] Implement unified header/footer linking both domains
- [ ] Validate all CTAs and doc links before production

### Phase 4: Marketing & Analytics (FUTURE)
- [ ] A/B test copy variants on each product page
- [ ] Track conversion metrics (CTAs clicked, docs visited, contact form submissions)
- [ ] Collect early user feedback on copy tone, clarity, messaging
- [ ] Refine based on user response

---

## Technical Architecture

### URL Structure

```
truexxiisupply.com (Marketing)
├── /                          (Main landing page)
├── #atlas-fab-product         (ATLAS FAB product section)
├── #mammoth-os-sdk            (MammothOS SDK product section)
└── #learning-platform         (Learning Platform product section)

command.truexxiisupply.com (Command Center)
├── /                          (Dashboard)
├── /atlas-fab                 (ATLAS FAB product page)
├── /sdk-quickstart            (SDK onboarding page)
├── /learning-platform-demo    (Learning Platform demo)
├── /contact?product=X         (Contact form)
└── /docs/*                    (Product documentation)
```

### Navigation Flow

#### From Marketing Site → Command Center
1. User reads ATLAS FAB section on truexxiisupply.com
2. Clicks "Explore ATLAS FAB" → `https://command.truexxiisupply.com/atlas-fab`
3. Lands on detailed product page with live feature preview
4. Clicks "View Technical Docs" → GitHub link
5. Clicks "See SDK on PyPI" → PyPI link

#### From Command Center → Marketing Site
1. User in command center wants brand/product overview
2. Clicks logo or footer link → `https://truexxiisupply.com`
3. Lands on main marketing page
4. Scrolls to relevant product section
5. Can re-engage with command center CTA

---

## File Manifest & Deployment

### Copy & Content Files (Ready)
- **`docs/product_landing_copy.md`** (15.9 KB)
  - All luxury copy, 3 product blocks, feature grids, use cases, brand guidelines
  - **Deploy to:** Git repo, accessible from product pages

- **`docs/product_landing_sections.html`** (26.8 KB)
  - Reusable HTML sections matching Tailwind + brand colors
  - 3 full product sections + cross-linking footer
  - **Deploy to:** Command center templates or `ui/` static assets

### Backend Integration Requirements

#### FastAPI Routes to Wire
1. **`/atlas-fab`** (GET)
   - Serve product landing page
   - Query params: `?ref=marketing` (track source)
   - Body: Hero copy, feature grid, pricing table, CTAs

2. **`/sdk-quickstart`** (GET)
   - Serve SDK onboarding page
   - Include code snippets, PyPI install command
   - Link to GitHub, docs, PyPI
   - Query params: `?tab=install|examples|docs` (default: install)

3. **`/learning-platform-demo`** (GET)
   - Serve curriculum builder preview
   - Optional: Embedded iframe with sample course
   - Link to docs, contact form

4. **`/contact?product=X`** (GET / POST)
   - Product selection dropdown (atlas-fab, sdk, learning-platform)
   - Form fields: email, company, inquiry
   - On success: Send to Slack/email, render thank-you page

#### Existing Routes to Update
- **`/api/modules`** — Add `atlas-fab`, `sdk`, `learning-platform` as discoverable products
- **`/api/agents`** — Ensure agents scoped per product context
- **`/api/workspace`** — Add product entitlement checks (future)

### Frontend Integration Requirements

#### Command Center (`ui/mad-architecht-command-center/src/`)
1. Update `App.jsx` navigation to include product links
2. Add `/product-landing` route type (non-chat, static content)
3. Implement `ProductCard` component for dashboard visibility
4. Add footer link back to truexxiisupply.com

#### Marketing Site (truexxiisupply.com HTML)
1. Integrate `product_landing_sections.html` into main page
2. Add cross-links from each product section to command center
3. Update footer with consistent branding and links
4. Add Google Analytics tracking for CTAs and section scrolls

---

## Copy Summary (Quick Reference)

### ATLAS FAB
- **Hero:** "Tutoring Precision. Every Learner."
- **Audience:** EdTech founders, training managers, product teams
- **Core Promise:** Embeddable adaptive tutoring + operator visibility
- **Primary CTA:** "Explore ATLAS FAB"
- **Secondary CTAs:** "View Technical Docs", "See SDK on PyPI"

### MammothOS SDK
- **Hero:** "Orchestrate. Reason. Scale."
- **Audience:** AI engineers, platform architects, developers
- **Core Promise:** Multi-agent orchestration + recursive reasoning + production safety
- **Primary CTA:** "Get Started with MammothOS"
- **Secondary CTAs:** "Read the Architecture Guide", "View on GitHub"

### Learning Platform
- **Hero:** "Knowledge That Adapts. Learners That Grow."
- **Audience:** Schools, corporate universities, field operations
- **Core Promise:** Adaptive curriculum + operator insights + field-ready deployment
- **Primary CTA:** "Launch a Learning Experience"
- **Secondary CTAs:** "Explore Curriculum Guides", "Request an Enterprise Demo"

---

## Brand Voice Consistency

### Tone Checklist
- ✅ Sophisticated, precise, operator-focused
- ✅ Specific capabilities over generic buzzwords
- ✅ Measurable outcomes, technical credibility
- ✅ Avoid: "smart AI", "powerful", "easy", "revolutionary"
- ✅ Use: "adaptive", "orchestration", "production-grade", "operator visibility"

### Color & Visual Guidelines
- **Primary CTA:** Ember (#c0392b) gradient to Amber
- **Secondary CTA:** Ember border, transparent bg, hover state opacity
- **Callout boxes:** Base-lighter bg with Ember/Amber borders
- **Feature cards:** Base-light bg, hover lift effect (transform -4px)
- **Text contrast:** 4.5:1 minimum for all body copy

### Link Destinations (Validated)
- PyPI package: `https://pypi.org/project/mammoth-os/`
- GitHub repo: `https://github.com/xxii-architect/mammoth_intro_ai`
- ATLAS FAB guide: `/blob/main/docs/atlas_fab_product_guide.md`
- MammothOS offering: `/blob/main/docs/mammoth_os_package_offering.md`
- ATLAS Manual: `/blob/main/ATLAS_MANUAL.md`
- Command center: `https://command.truexxiisupply.com`
- Contact form: `/contact?product=<product-id>`

---

## Success Metrics (To Track Post-Launch)

1. **Engagement**
   - CTAs clicked per product section
   - Docs opened from landing pages
   - Time spent on product pages

2. **Conversion**
   - Contact form submissions by product
   - GitHub stars / forks (repo visibility)
   - PyPI downloads (SDK adoption)

3. **SEO / Discovery**
   - Organic traffic to product pages
   - Keyword rankings (e.g., "adaptive tutoring SDK", "multi-agent orchestration Python")
   - Backlinks from edtech / AI publications

4. **Brand Sentiment**
   - User feedback on copy tone
   - Social share rate on product announcements
   - NPS on product clarity

---

## Deployment Checklist

- [ ] Copy finalized and approved (luxury tone, specificity, accuracy)
- [ ] HTML templates tested in local Tailwind environment
- [ ] Backend routes wired: `/atlas-fab`, `/sdk-quickstart`, `/learning-platform-demo`, `/contact`
- [ ] Frontend navigation updated with product links
- [ ] Cross-links validated: all URLs resolve correctly
- [ ] Marketing site updated with product sections and cross-links
- [ ] Footer links both domains consistently
- [ ] Analytics tracking configured for CTAs
- [ ] Early user testing on copy clarity and conversion intent
- [ ] Production deployment + smoke test all CTAs
- [ ] Announce product positioning (blog, social, press)

---

## Next Steps (Immediate)

1. **Backend:** Wire the three product landing endpoints (FastAPI)
2. **Frontend:** Add product navigation to Command Center
3. **Marketing:** Update truexxiisupply.com with product sections
4. **Validation:** QA all CTAs, doc links, and cross-domain navigation
5. **Launch:** Deploy to production and monitor early metrics

---

## Questions / Decisions

**Q: Should we white-label these sections for enterprise buyers?**
- **A:** Defer to Phase 4. Current positioning is product-standard; white-label variants can be added as separate URLs (e.g., `/atlas-fab?customer=acme-corp`) with custom branding.

**Q: Do we need separate docs sites or GitHub-only?**
- **A:** GitHub-only for now. Docs are in repo. Consider hosted docs (mkdocs, Docusaurus) in future if traffic justifies.

**Q: How do we handle pricing pages?**
- **A:** Pricing is currently a skeleton in each product guide. Landing pages show "Starting Free" + plan names only. Actual checkout wired later.

**Q: What about API documentation for SDK buyers?**
- **A:** Link to GitHub + PyPI. Full API docs can be generated with Sphinx or built into hosted docs later.

