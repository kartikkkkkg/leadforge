# Data & Privacy Considerations

## What LeadForge collects

Only **publicly available business information**: company name, website, industry,
location, address, phone, public email, public LinkedIn URL, and the source URL where
the information was found.

## What it never collects

- Passwords, credentials, or authentication-protected information
- Non-public personal data or sensitive personal information
- Anything behind a login wall

## Provider rules

- Respect `robots.txt`, website terms of service, rate limits, and API terms.
- No CAPTCHA bypassing. No anti-bot evasion. No access-control bypasses.
- If a source cannot be used legally or reliably, it is not used — the
  `ResearchProvider` abstraction exists so a compliant source/API can be plugged in.

## Demo data

All demo records are **synthetic**: `is_synthetic=True`, reserved `example.com`
domains, fictional `555-01XX` phone numbers, role-based emails only (`info@`,
`sales@`), no real personal names, and LinkedIn URLs are either `null` or on
`example.com` — never real third-party domains. The UI labels demo data with a
persistent **SYNTHETIC** badge, and it is never described as verified.

## Operator responsibilities

If you connect a real provider (Phase 6+), you are responsible for complying with that
provider's terms and with applicable privacy/data-protection law (e.g. GDPR/CCPA) for
your use case and jurisdiction.
