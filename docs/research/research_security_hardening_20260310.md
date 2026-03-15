# Security Hardening & Network Privacy Report

> Generated: 2026-03-10 | Status: RESEARCH REPORT
> Purpose: Harden Mac Mini server, protect network identity, prevent tracing

---

## Executive Summary

Analysis of network fingerprinting, macOS hardening, VPN/mesh security, and
operational security best practices. The goal: ensure the Mac Mini server and
all Permanence OS communications leave minimal trace and resist passive or
active surveillance. Key findings: WiFi is the biggest fingerprinting vector,
Tailscale already provides strong mesh encryption, and a short list of macOS
and Flask hardening steps will close the remaining gaps.

---

## 1. NETWORK FINGERPRINTING & ANTI-TRACING

### WiFi Fingerprinting (Biggest Risk)
- **MAC address**: Unique hardware identifier broadcast on every WiFi frame
- **Probe requests**: Devices broadcast SSIDs they've connected to before
- **Signal patterns**: Movement patterns trackable via WiFi triangulation
- **802.11 fingerprint**: Frame timing, capabilities, supported rates

**Mitigations**:
- **Turn off WiFi on Mac Mini entirely** — use Ethernet only. This eliminates
  the entire WiFi fingerprinting surface. The Mini is a server, it doesn't need WiFi.
  ```bash
  networksetup -setairportpower en0 off
  # Verify: networksetup -getairportpower en0
  ```
- **MAC randomization** (if WiFi ever needed): macOS 15+ supports per-network
  MAC randomization. Enable in Settings > WiFi > (network) > Private WiFi Address.
- **Disable probe requests**: With WiFi off, this is moot. If on, use
  `airport -z` to dissociate and stop probing.

### mDNS / Bonjour Suppression
- macOS broadcasts hostname, services, and device type via mDNS (Bonjour)
- Any device on the local network can discover the Mac Mini
- **Mitigation**: Disable mDNS advertisement
  ```bash
  sudo defaults write /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements -bool true
  # Restart mDNSResponder
  sudo killall -HUP mDNSResponder
  ```

### Hostname Anonymization
- Default hostname often contains owner name or device model
- **Mitigation**: Set generic hostname
  ```bash
  sudo scutil --set ComputerName "server"
  sudo scutil --set HostName "server"
  sudo scutil --set LocalHostName "server"
  ```

### DNS Privacy
- DNS queries reveal every domain accessed, even over VPN if DNS leaks
- **Mitigation**: DNS over HTTPS (DoH)
  - Configure in System Settings > Network > DNS
  - Use Cloudflare DoH: `https://1.1.1.1/dns-query`
  - Or NextDNS for filtering + privacy: `https://dns.nextdns.io/<config-id>`
  - Verify: `nslookup example.com` should resolve via encrypted DNS

---

## 2. macOS SYSTEM HARDENING

### FileVault (Full Disk Encryption)
- Encrypts entire boot volume at rest
- If Mac Mini is stolen, data is unreadable without password
- **Enable**: System Settings > Privacy & Security > FileVault > Turn On
- **Status check**: `fdesetup status`

### Firewall Configuration
- macOS has a built-in application firewall + pf packet filter
- **Enable stealth mode** (don't respond to pings or port scans):
  ```bash
  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
  ```
- **pf firewall rules** for strict port control:
  ```
  # /etc/pf.conf additions
  # Only allow SSH (22), Tailscale (41641/udp), and localhost services
  block in all
  pass in on lo0 all
  pass in proto tcp from any to any port 22
  pass in proto udp from any to any port 41641
  pass in on utun+ all  # Tailscale tunnel interface
  ```

### Automatic Updates
- Keep macOS and Xcode CLT updated for security patches
- Enable automatic security updates:
  ```bash
  sudo softwareupdate --schedule on
  defaults write com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool true
  ```

### Screen Lock & Login
- Auto-lock after 5 minutes of inactivity (even headless)
- Require password immediately after sleep
- Disable guest account

---

## 3. SSH HARDENING

### Current State
SSH is the lifeline between MacBook and Mac Mini. It must be both secure
and reliable. Key-based auth is already configured.

### Hardened sshd_config
```
# /etc/ssh/sshd_config additions
PasswordAuthentication no
ChallengeResponseAuthentication no
UsePAM no
PermitRootLogin no
MaxAuthTries 3
LoginGraceTime 30
AllowUsers permanence-os
ClientAliveInterval 120
ClientAliveCountMax 3
X11Forwarding no
AllowTcpForwarding yes  # needed for port forwarding
```

### SSH Key Security
- Current: ed25519 key (`~/.ssh/id_ed25519_mac_mini`) — good, strongest option
- Add passphrase if not already set (use ssh-agent for convenience)
- Consider: separate deploy key for agent GitHub operations (read-only)

### Fail2Ban Alternative
macOS doesn't have fail2ban natively, but:
- pf can rate-limit SSH connections:
  ```
  # In /etc/pf.conf
  table <bruteforce> persist
  block quick from <bruteforce>
  pass in proto tcp to any port 22 flags S/SA keep state \
    (max-src-conn 5, max-src-conn-rate 3/30, overload <bruteforce> flush global)
  ```
- This blocks IPs after 3 failed connections in 30 seconds

---

## 4. TAILSCALE SECURITY

### Current State
Tailscale mesh VPN is active. Mac Mini accessible at `100.118.168.26`.
This is already excellent — WireGuard-based encryption, no open ports needed.

### Additional Hardening
- **ACLs**: In Tailscale admin console, restrict which devices can reach
  the Mac Mini. Only allow MacBook + any future mobile devices.
- **Key expiry**: Set key expiry to 90 days (forces re-auth periodically)
- **MagicDNS**: Use Tailscale MagicDNS names instead of IPs for convenience
  (`paytons-mac-mini` instead of `100.118.168.26`)
- **Exit node**: If Mac Mini has a clean IP, it can serve as an exit node
  for the MacBook when on untrusted WiFi

### Tailscale + Services
- Services (Command Center :8000, Foundation :8787, API :8797) should bind
  to `127.0.0.1` not `0.0.0.0` — Tailscale handles routing
- This means services are ONLY accessible via Tailscale or localhost
- Never expose services on the LAN IP

---

## 5. FLASK / APPLICATION SECURITY

### Bind to Localhost
```python
# In dashboard_api.py
app.run(host="127.0.0.1", port=8000)  # NOT 0.0.0.0
```
Tailscale's subnet routing + SSH tunnels handle remote access.

### Security Headers
Add to Flask responses:
```python
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response
```

### Rate Limiting
- Install flask-limiter for API rate limiting
- Apply to sensitive endpoints (approval queue, command execution)
- Default: 60 requests/minute per IP

### Log Sanitization
- Never log full API keys, tokens, or passwords
- Truncate sensitive values: `sk-...last4`
- Rotate logs weekly, keep 4 weeks max

---

## 6. OUTBOUND MONITORING

### LuLu (Free macOS Firewall)
- Open-source outbound firewall for macOS
- Alerts on any new process attempting network access
- Install: `brew install --cask lulu`
- Catches unexpected phone-home behavior from any installed software

### Little Snitch (Paid Alternative)
- More polished UI, network monitor, map view
- Per-process rules with profiles
- $49 one-time purchase

### Recommendation
Start with LuLu (free). Upgrade to Little Snitch if deeper control needed.

---

## 7. OPERATIONAL SECURITY (OPSEC)

### Git Operations
- `python cli.py secret-scan --staged` before every push (already in workflow)
- `.gitignore` should include: `.env`, `*.pem`, `*.key`, `credentials.*`,
  `*.sqlite` (if contains sensitive data)
- Never commit Tailscale auth keys or SSH private keys
- Use git-crypt or SOPS for any config that must be versioned but is sensitive

### Environment Variables
- All secrets in `.env` files (never in code)
- `.env` files excluded from rsync and git
- Consider: HashiCorp Vault or `age` encryption for secrets at rest

### Backup Security
- Time Machine backups should be encrypted
- Remote backups (if any) should use encrypted transport
- Mac Mini's FileVault protects local data at rest

---

## 8. IMMEDIATE ACTIONS (Priority Order)

### This Week
1. **Turn off WiFi on Mac Mini** — single biggest fingerprinting fix
2. **Set generic hostname** — 30 seconds, eliminates name-based discovery
3. **Suppress mDNS** — stops Bonjour broadcasting
4. **Enable FileVault** — protects data at rest
5. **Enable stealth firewall** — stops responding to network probes
6. **Verify services bind to 127.0.0.1** — no LAN exposure

### This Month
7. **Harden sshd_config** — disable password auth, limit users
8. **Install LuLu** — monitor outbound connections
9. **Configure DNS over HTTPS** — encrypt DNS queries
10. **Add Flask security headers** — defense in depth
11. **Set up pf rate limiting** — SSH brute-force protection
12. **Configure Tailscale ACLs** — restrict device access

### Ongoing
- Review LuLu alerts weekly for unexpected outbound connections
- Rotate SSH keys annually
- Keep macOS updated (automatic security updates enabled)
- Audit `.env` files quarterly for stale credentials
- Monitor `/var/log/system.log` for unusual auth attempts

---

## 9. THREAT MODEL SUMMARY

| Threat | Risk | Mitigation |
|--------|------|------------|
| WiFi fingerprinting | HIGH | Disable WiFi, use Ethernet only |
| Local network discovery | MEDIUM | mDNS suppression + generic hostname |
| SSH brute force | LOW | Key-only auth + pf rate limiting |
| DNS surveillance | MEDIUM | DNS over HTTPS (Cloudflare/NextDNS) |
| Physical theft | MEDIUM | FileVault encryption |
| Service exposure | LOW | Bind to 127.0.0.1, Tailscale routing |
| Secret leakage | MEDIUM | Secret scanner + .gitignore + env vars |
| Outbound data exfil | LOW | LuLu monitoring + firewall rules |
| Man-in-the-middle | LOW | Tailscale WireGuard + SSH ed25519 |

---

*This report informs security decisions for Permanence OS infrastructure.*
*Implementation should be executed carefully — test SSH access after each*
*network change to avoid lockout.*
