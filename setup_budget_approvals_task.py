#!/usr/bin/env python3
"""Set up Mattermost backend and budget-approvals-q4 channel with test data."""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, '/home/jinli/Project/MobileWorld_fork/src')

from mobile_world.runtime.app_helpers import mattermost

def setup_budget_approvals_task():
    """Set up Mattermost backend and create the budget-approvals-q4 channel with test budget requests."""
    
    print("=" * 60)
    print("Mattermost Budget Approvals Task Setup")
    print("=" * 60)
    
    # Step 1: Start Mattermost backend
    print("\n[1/4] Starting Mattermost backend...")
    if not mattermost.start_mattermost_backend():
        print("✗ Failed to start Mattermost backend")
        return False
    
    print("✓ Mattermost backend started successfully")
    
    # Step 2: Login as admin
    print("\n[2/4] Logging in as admin...")
    cli = mattermost.MattermostCLI()
    if not cli.login(mattermost.ADMIN_ACCOUNT["username"], mattermost.ADMIN_ACCOUNT["password"]):
        print("✗ Failed to login as admin")
        return False
    
    print("✓ Logged in as admin")
    
    # Step 3: Create the budget-approvals-q4 channel
    print("\n[3/4] Creating budget-approvals-q4 channel...")
    cli.create_channel(
        team=mattermost.TEAM_NAME,
        channel_name="budget-approvals-q4",
        display_name="Budget Approvals Q4",
        private=False,
        purpose="Q4 Budget Request Reviews and Approvals",
        header="Department budget requests with ROI calculations",
    )
    print("✓ Created budget-approvals-q4 channel")
    
    # Step 4: Add test budget request messages with ROI calculations
    print("\n[4/4] Adding test budget requests with ROI calculations...")
    
    # Budget requests from different departments with NPV-based ROI calculations
    budget_requests = [
        {
            "department": "Engineering",
            "amount": 75000,
            "roi": 285.5,
            "message": """**Budget Request: Engineering Department - Q4**

**Requested Amount:** $75,000

**Project:** Cloud Infrastructure Upgrade

**NPV Calculation:**
- Initial Investment: $75,000
- Expected Cash Flows (3 years): $45,000, $52,000, $58,000
- Discount Rate: 8%
- NPV = -$75,000 + $45,000/(1.08) + $52,000/(1.08)² + $58,000/(1.08)³
- NPV = -$75,000 + $41,667 + $44,582 + $46,058 = **$57,307**

**Projected ROI:** 285.5% (NPV / Initial Investment × 100)

**Justification:** Critical infrastructure upgrade to support 3x traffic growth.
"""
        },
        {
            "department": "Marketing",
            "amount": 45000,
            "roi": 178.2,
            "message": """**Budget Request: Marketing Department - Q4**

**Requested Amount:** $45,000

**Project:** Digital Campaign Expansion

**NPV Calculation:**
- Initial Investment: $45,000
- Expected Cash Flows (2 years): $38,000, $42,000
- Discount Rate: 10%
- NPV = -$45,000 + $38,000/(1.10) + $42,000/(1.10)²
- NPV = -$45,000 + $34,545 + $34,711 = **$24,256**

**Projected ROI:** 178.2% (NPV / Initial Investment × 100)

**Justification:** Expand digital presence in emerging markets.
"""
        },
        {
            "department": "Research & Development",
            "amount": 120000,
            "roi": 342.8,
            "message": """**Budget Request: Research & Development - Q4**

**Requested Amount:** $120,000

**Project:** AI/ML Platform Development

**NPV Calculation:**
- Initial Investment: $120,000
- Expected Cash Flows (4 years): $55,000, $72,000, $88,000, $95,000
- Discount Rate: 12%
- NPV = -$120,000 + $55,000/(1.12) + $72,000/(1.12)² + $88,000/(1.12)³ + $95,000/(1.12)⁴
- NPV = -$120,000 + $49,107 + $57,398 + $62,656 + $60,355 = **$109,516**

**Projected ROI:** 342.8% (NPV / Initial Investment × 100)

**Justification:** Strategic investment in AI capabilities for competitive advantage.
"""
        },
        {
            "department": "Human Resources",
            "amount": 35000,
            "roi": 95.4,
            "message": """**Budget Request: Human Resources - Q4**

**Requested Amount:** $35,000

**Project:** Employee Training Program

**NPV Calculation:**
- Initial Investment: $35,000
- Expected Cash Flows (2 years): $22,000, $28,000
- Discount Rate: 8%
- NPV = -$35,000 + $22,000/(1.08) + $28,000/(1.08)²
- NPV = -$35,000 + $20,370 + $24,005 = **$33,375**

**Projected ROI:** 95.4% (NPV / Initial Investment × 100)

**Justification:** Upskilling workforce for digital transformation.
"""
        },
        {
            "department": "Operations",
            "amount": 62000,
            "roi": 215.3,
            "message": """**Budget Request: Operations Department - Q4**

**Requested Amount:** $62,000

**Project:** Warehouse Automation System

**NPV Calculation:**
- Initial Investment: $62,000
- Expected Cash Flows (3 years): $35,000, $42,000, $48,000
- Discount Rate: 9%
- NPV = -$62,000 + $35,000/(1.09) + $42,000/(1.09)² + $48,000/(1.09)³
- NPV = -$62,000 + $32,110 + $35,389 + $37,056 = **$42,555**

**Projected ROI:** 215.3% (NPV / Initial Investment × 100)

**Justification:** Automation to reduce operational costs by 30%.
"""
        },
        {
            "department": "Sales",
            "amount": 55000,
            "roi": 198.6,
            "message": """**Budget Request: Sales Department - Q4**

**Requested Amount:** $55,000

**Project:** CRM System Upgrade

**NPV Calculation:**
- Initial Investment: $55,000
- Expected Cash Flows (3 years): $32,000, $38,000, $42,000
- Discount Rate: 10%
- NPV = -$55,000 + $32,000/(1.10) + $38,000/(1.10)² + $42,000/(1.10)³
- NPV = -$55,000 + $29,091 + $31,405 + $31,557 = **$37,053**

**Projected ROI:** 198.6% (NPV / Initial Investment × 100)

**Justification:** Enhanced CRM to improve sales conversion by 25%.
"""
        },
    ]
    
    # Post each budget request
    for request in budget_requests:
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="budget-approvals-q4",
            message=request["message"],
        )
        print(f"  ✓ Posted {request['department']} budget request (${request['amount']:,}, ROI: {request['roi']}%)")
    
    cli.logout()
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print("\nChannel: budget-approvals-q4")
    print("Team: neuralforge")
    print("\nLogin Credentials:")
    print("  Email: sam.oneill@neuralforge.ai")
    print("  Password: password")
    print("\nBudget Requests Summary:")
    print("  - Engineering: $75,000 (ROI: 285.5%) - Executive Required")
    print("  - Marketing: $45,000 (ROI: 178.2%) - Standard")
    print("  - R&D: $120,000 (ROI: 342.8%) - Executive Required")
    print("  - HR: $35,000 (ROI: 95.4%) - Standard")
    print("  - Operations: $62,000 (ROI: 215.3%) - Executive Required")
    print("  - Sales: $55,000 (ROI: 198.6%) - Executive Required")
    print("\nHighest ROI: Research & Development (342.8%)")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = setup_budget_approvals_task()
    if not success:
        sys.exit(1)
