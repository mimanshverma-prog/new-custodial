# VPS Provider Recommendations for Bulk Email (Self-Hosted)

**Date:** February 2026
**Purpose:** Identifying the best hosting providers that allow **Port 25 (SMTP)** for sending email.

## ⚠️ Critical Warning
Most Cloud Providers (AWS, Google Cloud, Azure, DigitalOcean, Linode, Vultr) **BLOCK Port 25 by default** for new accounts to prevent spam. Unblocking it is often impossible for new users.

**Do NOT use these providers for this project.**

---

## Top Recommendations

### 1. Contabo (Best Overall for Beginners)
*   **Product:** Cloud VPS S (or M)
*   **Port 25 Policy:** Generally open. If blocked, support usually unblocks it upon request with a valid justification (e.g., "Hosting a newsletter for my company").
*   **Specs (approx):** 4 vCPU, 8GB RAM, 50GB NVMe.
*   **Cost:** ~€5 - €6 / month ($5.50 - $6.50).
*   **Pros:** Very cheap, high RAM, lenient Port 25 policy.
*   **Cons:** Older hardware in some regions, support can be slow.

### 2. Hetzner (Best Performance, stricter policy)
*   **Product:** Cloud CX22 or CPX11
*   **Port 25 Policy:** **BLOCKED by default for new accounts.**
    *   **Unblocking:** You must pay your first invoice (wait 1 month) and then submit a "Limit Request" to open Port 25.
    *   *Workaround:* Buy a "Dedicated Server" (Auction) instead of Cloud, but that is more expensive (€30+).
*   **Specs:** 2 vCPU, 4GB RAM.
*   **Cost:** ~€4 - €5 / month.
*   **Pros:** Excellent performance, German reliability.
*   **Cons:** You might have to wait 1 month to send emails.

### 3. OVHcloud (Hit or Miss)
*   **Product:** VPS Starter / Value
*   **Port 25 Policy:** Often blocked on newer "Local Zone" VPS ranges. Older ranges might work, but support is notoriously unhelpful for unblocking.
*   **Cost:** ~€4 - €6 / month.
*   **Verdict:** Risky. Only use if Contabo/Hetzner reject you.

---

## Action Plan

1.  **Sign up for Contabo (Cloud VPS S).**
2.  **During checkout:** Use a real address and identity (they verify manually).
3.  **After setup:**
    *   SSH into the server.
    *   Run `telnet gmail-smtp-in.l.google.com 25`.
    *   **If it connects:** You are good to go!
    *   **If it times out:** Contact support: *"I need Port 25 unblocked to send transactional emails for my business zateway.com."*

## Hardware Requirements for 1M Emails/Day

| Resource | Requirement | Reason |
| :--- | :--- | :--- |
| **CPU** | 4 vCPU | Parsing HTML, DKIM signing, and database writes. |
| **RAM** | 8 GB | Running Postfix, Database, and Python API efficiently. |
| **Storage** | 50GB NVMe | Storing logs and contact lists. |
| **Bandwidth** | 32TB (Contabo) | 1M emails/day is ~100GB/month. Plenty of room. |

**Final Choice:** Go with **Contabo Cloud VPS S**. It is the most cost-effective and easiest path to an open Port 25.
