# Enterprise-Grade Distributed Email Delivery System (1M/Day)

This document outlines the architecture for a scalable, high-throughput email delivery system capable of sending 1,000,000 emails per day while maintaining high deliverability and compliance.

## 1. Throughput Planning

To send **1,000,000 emails/day**, we must account for non-peak hours and potential throttling.

*   **Average Daily Throughput:**
    *   1,000,000 emails / 24 hours = 41,666 emails/hour
    *   41,666 / 60 = **~695 emails/minute**
    *   695 / 60 = **~11.6 emails/second**

*   **Peak Throughput Requirement:**
    *   Marketing emails are often sent in bursts (e.g., 9 AM - 5 PM).
    *   Assuming an 8-hour sending window: 1M / 8h = **125,000 emails/hour** (~35 emails/sec).
    *   **Recommended Capacity:** Plan for **50-100 emails/second** to handle bursts and retry queues.

*   **IP Warming & Capacity:**
    *   A fresh IP can safely send ~50-100 emails/day initially.
    *   A fully warmed IP can handle ~100k-500k emails/day depending on reputation.
    *   **Recommendation:** Start with **5-10 Dedicated IPs** rotated via Round Robin to spread volume and risk.

## 2. Infrastructure Architecture

### IP & Domain Strategy
*   **IP Pools:**
    *   **Transactional Pool (High Priority):** 2 IPs (Password resets, Order confirms). High reputation critical.
    *   **Marketing Pool (Bulk):** 4-8 IPs (Newsletters, Promos). Higher volume, slightly lower priority.
*   **Domain Isolation:**
    *   Use subdomains for different streams:
        *   `auth.yourdomain.com` (Transactional)
        *   `news.yourdomain.com` (Marketing)
        *   `promos.yourdomain.com` (Aggressive Marketing)

### DNS Configuration
Every sending domain/subdomain MUST have:
*   **SPF (Sender Policy Framework):** `v=spf1 ip4:1.2.3.4 ip4:1.2.3.5 -all`
*   **DKIM (DomainKeys Identified Mail):** 2048-bit RSA keys signed by the MTA.
*   **DMARC (Domain-based Message Authentication):** `v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com`
*   **rDNS (Reverse DNS/PTR):** Crucial. The IP `1.2.3.4` must resolve to `mta1.yourdomain.com`, and `mta1.yourdomain.com` must resolve back to `1.2.3.4`.

## 3. Mail Transfer Layer (MTA)

The core sending engine (Postfix/PowerMTA) handles the SMTP protocol.

*   **Connection Pooling:** Reuse SMTP connections to major ISPs (Gmail/Outlook) to avoid "Too many connections" errors.
*   **Throttling Policies:**
    *   **Gmail:** Max ~25-50 concurrent connections.
    *   **Yahoo:** strict rate limits per hour.
    *   **Hotmail/Outlook:** Very strict on grey-listing.
*   **Queue Management:**
    *   **Active Queue:** Emails currently being sent.
    *   **Deferred Queue:** Soft bounces (temporary failures like "Inbox Full").
    *   **Retry Logic:** Exponential backoff (retry at 1m, 5m, 15m, 1h, 4h, etc.).
*   **Virtual MTA (vMTA):** Configure Postfix to bind specific campaigns to specific IPs.

## 4. Distributed Processing Architecture

```mermaid
graph TD
    A[Client App / API] -->|HTTP POST| B[Load Balancer (Nginx)]
    B --> C[API Servers (FastAPI)]
    C -->|Produce| D[Message Queue (RabbitMQ/Kafka)]

    subgraph "Worker Cluster"
        E[Worker 1]
        F[Worker 2]
        G[Worker 3]
    end

    D -->|Consume| E
    D -->|Consume| F
    D -->|Consume| G

    subgraph "MTA Layer (Postfix)"
        H[MTA Node 1 (IP: 1.2.3.4)]
        I[MTA Node 2 (IP: 1.2.3.5)]
    end

    E -->|SMTP| H
    F -->|SMTP| H
    G -->|SMTP| I

    H -->|Internet| J[Gmail/Yahoo/Outlook]
    I -->|Internet| J

    J -->|Webhooks (Bounce/Complaint)| C
```

*   **API Layer:** Accepts JSON payload, validates request, pushes to Queue.
*   **Message Queue:** Decouples ingestion from sending. Ensures no data loss if MTA is slow.
*   **Workers:** Fetch jobs, render HTML (Jinja2), and inject into MTA via SMTP.
*   **Horizontal Scaling:** Add more Workers/MTA nodes as volume grows.

## 5. Reputation & Safety Controls

*   **Bounce Handling:**
    *   **Hard Bounce (User Unknown):** Immediately mark contact as `Invalid` in DB. **NEVER** retry.
    *   **Soft Bounce (Mailbox Full):** Retry for 24-48 hours, then mark `Inactive`.
*   **Feedback Loops (FBL):**
    *   Register with Google Postmaster Tools, Microsoft SNDS.
    *   Process "Complaint" webhooks to immediately Unsubscribe users who mark as spam.
*   **Circuit Breakers:**
    *   If `Bounce Rate > 5%` or `Complaint Rate > 0.1%` in the last hour -> **PAUSE CAMPAIGN AUTOMATICALLY**.

## 6. Monitoring & Observability

*   **Metrics (Prometheus/Grafana):**
    *   Throughput (Sent/sec).
    *   Latency (Time in Queue).
    *   Delivery Rates (Sent vs Bounced).
    *   Queue Depth (Postfix queue size).
*   **Logging (ELK/Graylog):**
    *   Centralized logs for every SMTP transaction ID.
    *   Searchable history for customer support ("Why didn't I get my email?").

## 7. Risk & Compliance

*   **Legal:**
    *   **CAN-SPAM:** Must have physical address + One-click Unsubscribe link.
    *   **GDPR:** Consent records, "Right to be Forgotten".
*   **Warm-up Strategy (Example for New IP):**
    *   **Day 1:** 50 emails (Manual/Friends).
    *   **Day 2:** 100 emails.
    *   **Day 3:** 200 emails.
    *   **Day 4:** 400 emails.
    *   **Day 5:** 1,000 emails.
    *   **Day 10:** 10,000 emails.
    *   **Day 20:** 100,000 emails.
    *   *Note: Volume doubles roughly every 2-3 days if reputation stays high.*

## 8. Failure Scenarios

| Scenario | Mitigation |
| :--- | :--- |
| **IP Blacklisted** | Stop sending immediately. Request delisting. Switch traffic to backup IP pool. |
| **MTA Crash** | Queue (RabbitMQ) holds messages until MTA restarts. Redundant MTAs prevent downtime. |
| **Database Failure** | Read replicas for high availability. Redis for caching. |
| **Spam Spike** | Automated "Circuit Breaker" pauses account if complaints spike. |
