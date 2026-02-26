# Bulk Email Server (Self-Hosted)

A complete, self-hosted solution for sending bulk emails (1 Million+/day) without relying on expensive SaaS platforms like Mailchimp or Instantly.ai.

**Features:**
*   **Backend:** Python (FastAPI) + SQLite (for high speed).
*   **Frontend:** Vue.js Dashboard (Upload CSV, Create HTML Campaigns).
*   **Sending Engine:** Local Postfix Server (Optimized for Bulk).
*   **Reputation Management:** Throttling built-in to warm up IPs.

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
*   Day 1: 500 emails
*   Day 2: 1,000 emails
*   Day 3: 2,500 emails
*   Day 4: 5,000 emails
*   ...Double every few days until you reach 1M.

## License
MIT
