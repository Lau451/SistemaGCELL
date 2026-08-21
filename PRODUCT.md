# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primarily walk-in and social-media customers of GCELL, a local retail store selling phones and consumer tech. Majority of the customer base is women. They come to browse available stock, compare products, and decide what to ask about — not to complete an online purchase (no checkout exists yet).

## Product Purpose

A public catalog for GCELL's phone/tech inventory: browse, search, filter, and view product detail. Success is a visitor finding a product and taking the next step (contacting the store) with enough confidence to act.

## Positioning

Local retail store, not a marketplace or wholesaler. The catalog exists to drive a personal conversation (WhatsApp/Instagram) rather than a self-serve transaction — trust and clarity matter more than raw SKU volume.

## Operating Context

Customer journey: browse catalog (search/filter) → open product detail → tap a WhatsApp or Instagram button to consult/reserve/buy. Purchase and payment currently happen off-platform (chat or in-store); online payments are planned for later but out of scope for this design pass. A separate admin back-office (already built, AI-assisted product copy/alt-text) manages the same product data — out of scope for this catalog surface.

## Capabilities and Constraints

- No cart/checkout exists yet (`frontend/src` has no `/cart`, `/checkout`, or `/order` route) — confirmed via prior session grep.
- Contact-to-buy is the only conversion path for now: WhatsApp and Instagram, product-aware (deep-link/prefill where possible).
- Built on Next.js; UI has been functional but intentionally unpolished until now.

## Brand Commitments

No existing logo, color system, or visual identity — GCELL is open to a new one being proposed. One confirmed steer: the customer base skews female, and pink is a welcome (not mandatory) palette element — to be executed with tech credibility, not a generic pastel/kids treatment.

## Evidence on Hand

No real product photos, logo, or brand assets confirmed available yet. Mockup content (product names, prices, images) will be illustrative/synthetic and labeled as such — not to be read as real inventory or pricing claims.

## Product Principles

- Personal-shop trust over marketplace scale: design for "ask a person," not "add to cart."
- Respect the audience without stereotyping it: confident, tech-credible, warm — not infantilized.
- Catalog browsing (search/filter) is a task (Operate); product detail closes on a contact decision (Persuade).
- Payments are a known future extension — leave room, don't design against it.
