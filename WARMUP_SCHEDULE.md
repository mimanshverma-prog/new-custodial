# IP Warmup Schedule (0 to 1 Million)

This guide outlines a strict schedule for warming up a fresh dedicated IP address to reach high-volume sending capacity. Following this schedule minimizes the risk of IP blocking and spam filtering.

## Why Warmup?
ISPs (Gmail, Yahoo, Outlook) filter unknown IPs aggressively. "Warming up" proves you are a legitimate sender by gradually increasing volume and maintaining high engagement (opens/clicks) and low complaints.

## Configuration
In `docker-compose.yml`, set `EMAILS_PER_SECOND` based on your current volume.
*   **Initial:** `0.01` (very slow)
*   **Week 2:** `0.1`
*   **Month 2:** `1.0` (1 email/sec)
*   **Target (1M/day):** `12.0` (12 emails/sec)

## The Schedule (Standard 8-Week Plan)

| Day | Max Volume | Hourly Rate | Target Audience |
| :--- | :--- | :--- | :--- |
| **Day 1** | 50 | 5 | Internal Team / Friends |
| **Day 2** | 100 | 10 | Most Active Users (opened last 30 days) |
| **Day 3** | 200 | 20 | Most Active Users |
| **Day 4** | 400 | 40 | Most Active Users |
| **Day 5** | 500 | 50 | Active Users |
| **Day 6** | 1,000 | 100 | Active Users |
| **Day 7** | 2,000 | 200 | Active Users |
| **Week 2** | 5,000 | 500 | Active Users |
| **Week 3** | 10,000 | 1,000 | Active + Recent Signups |
| **Week 4** | 20,000 | 2,000 | Full List |
| **Week 5** | 40,000 | 4,000 | Full List |
| **Week 6** | 80,000 | 8,000 | Full List |
| **Week 7** | 160,000 | 16,000 | Full List |
| **Week 8** | 320,000 | 32,000 | Full List |
| **Month 3** | 1,000,000 | 100,000 | Full List |

## Critical Rules

1.  **Monitor Reputation Daily:** Use [Google Postmaster Tools](https://postmaster.google.com/) to check your domain reputation. If it drops to "Low" or "Bad", **PAUSE** immediately.
2.  **Remove Complaints:** If someone marks spam, unsubscribe them instantly.
3.  **Process Bounces:** Remove Hard Bounces immediately. High bounce rates (>5%) kill reputation.
4.  **Content Matters:** Don't change your "From Name" or "Subject Line" style drastically during warmup.
5.  **Engagement is Key:** If open rates drop below 15-20%, stop increasing volume. Clean your list.

## Troubleshooting

*   **Blocked by Outlook/Hotmail?** They are the strictest. Join their [SNDS Program](https://sendersupport.olc.protection.outlook.com/snds/).
*   **Blocked by Gmail?** Check your SPF/DKIM/DMARC alignment. Ensure you aren't sending to inactive accounts (spam traps).
