"""
Seed script — populates brand_knowledge collection with NowPurchase company data.
Safe to re-run: clears brand_knowledge entries with source='seed_script' first,
then re-writes all entries. Does not touch agent_memory.
"""

import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from backend.storage.chromadb_client import get_chroma_client

SEED_DATA = [
    # ── COMPANY INFO ──────────────────────────────────────────────────

    {
        "content": "NowPurchase is a Kolkata-based AI-powered B2B platform serving India's $19 billion foundry and castings industry. Founded in 2017 by Naman Shah (CEO) and Aakash Shah (Co-founder). Total funding: approximately ₹120 crore ($18M USD). Latest round of ₹80 crore was led by Bajaj Finserv in April 2026, with participation from Info Edge Ventures, Orios Venture Partners, and REAL Group.",
        "category": "company_info",
        "topic": "company overview and funding"
    },
    {
        "content": "NowPurchase has two business verticals: (1) MetalCloud — a SaaS AI platform for metal manufacturers, and (2) a raw material procurement marketplace where foundries can source scrap, alloys, and additives. The company also operates a network of scrap processing centres and offers branded products for alloys and additives.",
        "category": "company_info",
        "topic": "business verticals"
    },
    {
        "content": "NowPurchase leadership: Naman Shah is the Founder and CEO. Aakash Shah is Co-founder. Ankan Adhikari is CTO. Headquartered in Kolkata, West Bengal, India.",
        "category": "team_info",
        "topic": "founders and leadership"
    },
    {
        "content": "NowPurchase has delivered over 1.95 lakh tonnes of materials to 200+ clients. MetalCloud is deployed across 250+ factories nationwide, with clients including Titagarh Rail Systems Limited and Brakes India. 2x year-over-year growth over three years.",
        "category": "company_info",
        "topic": "scale and key metrics"
    },

    # ── PRODUCT INFO ──────────────────────────────────────────────────

    {
        "content": "MetalCloud is NowPurchase's AI-powered SaaS platform — the core operating system for metal manufacturers. Key features: charge mix optimization, real-time heat data and analytics, quality monitoring, production process optimization, IoT and computer vision for shop-floor digitization.",
        "category": "product_info",
        "topic": "MetalCloud product features"
    },
    {
        "content": "MetalCloud's charge mix optimizer uses AI to give real-time recommendations on what raw materials to add to the furnace to achieve the desired target chemistry. Customers report 2-5% cost savings per heat and significant reductions in melt time.",
        "category": "product_info",
        "topic": "MetalCloud charge mix optimizer outcomes"
    },
    {
        "content": "MetalCloud provides real-time WhatsApp integration for foundry operators — heat-wise updates, dilution suggestions, and raw material pricing delivered directly on WhatsApp. This is a key adoption driver for factory floor workers.",
        "category": "product_info",
        "topic": "MetalCloud WhatsApp integration"
    },
    {
        "content": "MetalCloud uses computer vision (YOLO models, OpenCV, Raspberry Pi edge devices) for anomaly detection on factory floors — detecting process inefficiencies and reducing downtime by 7-10%.",
        "category": "product_info",
        "topic": "MetalCloud computer vision features"
    },

    # ── MATERIAL INFO ──────────────────────────────────────────────────

    {
        "content": "NowPurchase procures and supplies these raw materials to foundries: Ferro Alloys (FeSi, FeMn, FeCr, FeMo), Additives (inoculants, nodularizers, carburizers), Scrap Metal (MS scrap, CI scrap), Pig Iron, and branded private-label alloy and additive products.",
        "category": "material_info",
        "topic": "raw materials supplied"
    },
    {
        "content": "NowPurchase offers real-time pricing and stock availability for all raw materials through WhatsApp bot and MetalCloud. Foundries can check current market prices for ferro alloys, scrap, and pig iron without calling suppliers.",
        "category": "material_info",
        "topic": "real-time pricing and procurement"
    },

    # ── BRAND VOICE ──────────────────────────────────────────────────

    {
        "content": "NowPurchase brand voice: Authoritative, precise, and confident. The audience is engineering professionals — foundry managers, metallurgists, factory owners. Speak in outcomes and data. Always specific: '23% reduction in scrap' not 'significant scrap reduction'. Never casual, never aggressive. No emojis in headlines.",
        "category": "brand_voice",
        "topic": "brand voice and tone"
    },
    {
        "content": "NowPurchase key messages: (1) AI-powered precision for foundry operations, (2) Reduce costs and improve quality with data-driven decisions, (3) From procurement to production — one platform, (4) Trusted by 250+ factories across India, (5) The operating system for modern metal manufacturing.",
        "category": "brand_voice",
        "topic": "key marketing messages"
    },

    # ── DESIGN RULES — DARK MODE ──────────────────────────────────────

    {
        "content": "NowPurchase DARK MODE post design language: Deep navy background (#020C13 to #041826). Primary blue accent (#1579BE). White text on dark surfaces (#FFFFFF primary, rgba(255,255,255,0.75) secondary). Glassmorphism containers with rgba(0,0,0,0.62) fill and backdrop blur 16px. White gradient border (28% opacity top, 8% sides). Inner white highlight on top edge (18% opacity). Foundry or factory background imagery — dark, moody, cinematic. Urbanist ExtraBold for headlines, Oxanium for body.",
        "category": "design_rules_dark",
        "topic": "dark mode complete design language"
    },
    {
        "content": "NowPurchase DARK MODE glass card spec: background rgba(0,0,0,0.62), border top rgba(255,255,255,0.28), border sides/bottom rgba(255,255,255,0.08), inner highlight rgba(255,255,255,0.18), drop shadow 0 8px 32px rgba(0,0,0,0.45), corner radius 24px. Logo pill: rgba(0,0,0,0.60) fill, rgba(255,255,255,0.20) border, 100px corner radius. White (white version) logo on dark glass.",
        "category": "design_rules_dark",
        "topic": "dark mode glassmorphism specification"
    },
    {
        "content": "NowPurchase DARK MODE background imagery: Foundry or factory environment. Dark, moody, cinematic photography style. 3D CGI quality abstract industrial forms. Shallow depth of field with strongly blurred background elements. Subtle dark gradient in centre zone where glass card sits. No text, no faces, no logos. Target luminance: centre zone ≤ 0.40. Use assets/backgrounds/dark/ library.",
        "category": "design_rules_dark",
        "topic": "dark mode background imagery requirements"
    },

    # ── DESIGN RULES — LIGHT MODE ──────────────────────────────────────

    {
        "content": "NowPurchase LIGHT MODE post design language: Light grey/white background (#F2F2F2 to #FFFFFF). Primary blue accent (#1579BE) remains. Dark text on light surfaces (#0D0D0D primary, rgba(0,0,0,0.65) secondary). Glassmorphism containers with rgba(255,255,255,0.78) fill and backdrop blur 16px. Dark gradient border (12% opacity top, 5% sides). Near-white inner highlight on top edge. Minimal, airy, clean abstract industrial background imagery. Urbanist ExtraBold for headlines, Oxanium for body. Dark (dark version) logo on light glass.",
        "category": "design_rules_light",
        "topic": "light mode complete design language"
    },
    {
        "content": "NowPurchase LIGHT MODE glass card spec: background rgba(255,255,255,0.78), border top rgba(0,0,0,0.12), border sides/bottom rgba(0,0,0,0.05), inner highlight rgba(255,255,255,0.90), drop shadow 0 8px 32px rgba(0,0,0,0.12), corner radius 24px. Logo pill: rgba(255,255,255,0.75) fill, rgba(0,0,0,0.10) border, 100px corner radius. Dark (dark version) logo on light glass.",
        "category": "design_rules_light",
        "topic": "light mode glassmorphism specification"
    },
    {
        "content": "NowPurchase LIGHT MODE background imagery: Minimal abstract industrial environment. Soft diffused light. Clean airy atmosphere. Abstract 3D CGI industrial forms with light tones. Out-of-focus depth of field. Sophisticated clean background without heavy shadows or dramatic moody lighting. No text, no faces, no logos. Target luminance: centre zone ≥ 0.72. Use assets/backgrounds/light/ library.",
        "category": "design_rules_light",
        "topic": "light mode background imagery requirements"
    },

    # ── LOGO GUIDELINES ──────────────────────────────────────────────

    {
        "content": "Logo type guidelines: Use 'nowpurchase' logo type for company-wide brand communications, funding announcements, team/culture posts, and general awareness. Use 'metalcloud' logo type for product feature posts, case studies, and MetalCloud-specific content. Use 'combined' logo type when the post references both the procurement/materials business and the MetalCloud platform together. The combined logo is a pre-designed lockup (not composed at runtime).",
        "category": "logo_guidelines",
        "topic": "when to use each logo type"
    },
    {
        "content": "Logo placement law: Logo always at top-center inside a glassmorphism pill. Pill uses hug_content sizing — width equals logo width plus 48px horizontal padding. Minimum pill width: 160px. Pill height: 56px. Corner radius: 100px (full pill shape). Logo vertically centered in pill. Top of pill at 72px from canvas top edge. For combined logo, the pill widens automatically to fit the pre-designed combined PNG.",
        "category": "logo_guidelines",
        "topic": "logo placement and pill sizing rules"
    },

    # ── CUSTOMER INFO ──────────────────────────────────────────────────

    {
        "content": "Notable NowPurchase customers: Titagarh Rail Systems Limited (railway components), Brakes India (automotive brakes), Real Ispat Group (investor and customer). Serves 250+ factories across India in automotive, infrastructure, and heavy machinery sectors.",
        "category": "customer_info",
        "topic": "key customers"
    },
    {
        "content": "NowPurchase competitive differentiators: (1) Deep focus on metal manufacturing specifically, (2) Integrated SaaS platform MetalCloud alongside procurement, (3) AI-powered optimization built into the workflow, (4) Own scrap processing network and branded products, (5) On-ground service teams for quality assurance.",
        "category": "company_info",
        "topic": "competitive differentiation"
    }
]


def seed():
    client = get_chroma_client()
    existing = client.list_documents(
        "brand_knowledge",
        filters={"source": {"$eq": "seed_script"}}
    )
    if existing:
        print(f"  Removing {len(existing)} existing seed entries...")
        for entry in existing:
            client.delete_document("brand_knowledge", entry["id"])

    print(f"Seeding {len(SEED_DATA)} entries into brand_knowledge...\n")
    for i, entry in enumerate(SEED_DATA, 1):
        doc_id = f"bk_seed_{uuid.uuid4().hex[:10]}"
        client.add_document(
            collection="brand_knowledge",
            document=entry["content"],
            metadata={
                "category": entry["category"],
                "topic": entry["topic"],
                "added_by": "seed_script",
                "added_at": datetime.now(timezone.utc).isoformat(),
                "verified": True,
                "source": "seed_script"
            },
            doc_id=doc_id
        )
        print(f"  [OK] [{i:02d}] {entry['topic']}")

    total = client.brand_knowledge.count()
    print(f"\nSeed complete. brand_knowledge now contains {total} entries.")
    print(f"agent_memory contains {client.agent_memory.count()} entries (should be 0).")

    # Smoke-test query
    results = client.query_collection("brand_knowledge", "MetalCloud charge mix optimizer", n=3)
    print(f"\nSmoke-test query 'MetalCloud charge mix optimizer' -> {len(results)} result(s)")
    for r in results:
        print(f"  [{r['metadata']['category']}] {r['metadata']['topic']} (distance: {r['distance']:.3f})")


if __name__ == "__main__":
    seed()
