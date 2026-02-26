# Bulk Email Server (Self-Hosted)

A complete, self-hosted solution for sending bulk emails (1 Million+/day) without relying on expensive SaaS platforms like Mailchimp or Instantly.ai.

**⚠️ Enterprise Architecture Note:**
This repository provides the **Single Node Implementation** of the [Enterprise Distributed Architecture](ARCHITECTURE.md). For scaling to 1M+ emails/day in a production environment, please review the `ARCHITECTURE.md` document for details on clustering, IP pools, and queue management.

**Features:**
*   **Backend:** Python (FastAPI) + SQLite (for high speed).
*   **Frontend:** Vue.js Dashboard (Upload CSV, Create HTML Campaigns).
*   **Sending Engine:** Local Postfix Server (Optimized for Bulk).
*   **Reputation Management:** Configurable rate limiting for IP warmup.
*   **Documentation:** Comprehensive [Architecture Guide](ARCHITECTURE.md).
*   **Warm-Up:** Step-by-step [Warm-Up Schedule](WARMUP_SCHEDULE.md).

## Prerequisites

1.  **A VPS (Virtual Private Server):**
    *   **Provider:** Hetzner, Contabo, or OVH (Allow Port 25). **Do not use AWS/GCP/Azure** (they block Port 25).
    *   **OS:** Ubuntu 20.04 or 22.04.
    *   **Specs:** 2 vCPU, 4GB RAM is enough for 1M emails.

2.  **A Domain Name:**
    *   e.g., `yourmarketing.com`.

## Installation Guide

### 1. Setup the VPS (Postfix)
Connect to your VPS via SSH and run the setup script:

```bash
# Clone this repo (or upload files)
git clone <repo_url>
cd bulk-email-server

# Run the setup script as root
sudo bash setup_server.sh
```

Follow the on-screen instructions to set your hostname (e.g., `mail.yourdomain.com`).

### 2. Configure DNS Records (CRITICAL)
To avoid spam folders, add these TXT records to your Domain Registrar (GoDaddy, Namecheap, etc.):

| Type | Host | Value |
| :--- | :--- | :--- |
| **A** | `mail` | `<YOUR_VPS_IP>` |
| **MX** | `@` | `10 mail.yourdomain.com` |
| **TXT** | `@` | `v=spf1 mx ip4:<YOUR_VPS_IP> -all` |
| **TXT** | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:admin@yourdomain.com` |

*Note: The script will help you generate the DKIM record.*

### 3. Run the Application (Docker)
Ensure Docker is installed, then:

```bash
docker-compose up -d --build
```

The dashboard will be available at `http://<YOUR_VPS_IP>:8000`.

## How to Send 1 Million Emails

1.  **Open Dashboard:** Go to `http://<YOUR_VPS_IP>:8000`.
2.  **Upload Contacts:** Upload a CSV file with `email` and `name` columns.
3.  **Create Campaign:** Write your HTML email. Use `{{name}}` for personalization.
4.  **Start:** Click "Send".

The system will queue emails and send them via Postfix.

## Warm-up Strategy (Don't skip!)
Please refer to [WARMUP_SCHEDULE.md](WARMUP_SCHEDULE.md) for the detailed day-by-day plan to reach 1 Million emails/day safely.

## License
MIT
