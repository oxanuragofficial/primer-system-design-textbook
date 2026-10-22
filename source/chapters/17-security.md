%part Part VI | Security and Operations | Protecting systems and their users, then running them, observing them and paying for them.
%derived Notebook chapter 9 (security basics: encrypt in transit and at rest, sanitise input, parameterised queries, least privilege)
%added threat modelling, authentication versus authorization in depth, passwords and tokens, OAuth 2.0 flow, injection and web attacks, secrets and key management, abuse prevention, privacy engineering, audit logging
# Security and Privacy {#ch-security}

::: objectives
After this chapter you can:

- do a small threat model for a design and name the main attack classes;
- distinguish authentication from authorization and describe how passwords, sessions, tokens and OAuth 2.0 fit together;
- prevent injection, cross-site scripting, request forgery and broken access control;
- explain encryption in transit and at rest, key management and secrets handling;
- apply least privilege, abuse prevention and privacy-by-design practices, including data retention and deletion.
:::

::: prereq
Chapters {ch:ch-network} (TLS, HTTP), {ch:ch-api} (status codes, API design), {ch:ch-entry} (gateway, rate limiting) and {ch:ch-sql}.
:::

::: terms
Authentication (AuthN)
: Proving *who* you are.

Authorization (AuthZ)
: Deciding *what* an identified party may do.

Least privilege
: Giving each person and program only the access it needs, no more.

Encryption at rest / in transit
: Protecting stored data, and data moving across a network.

Secret
: A credential (password, API key, private key, token) that must stay confidential.

PII (personally identifiable information)
: Data that can identify a person: name, email, phone, address, device identifiers.
:::

## Thinking like an attacker {#sec-threat}

Security is not a feature to bolt on; it is a property to design for. The cheapest technique is a **threat model**: before building, ask four questions: *What are we protecting?* (user data, money, availability, reputation) *Who might attack, and how?* (anonymous internet users, malicious customers, insiders, stolen laptops, compromised dependencies) *What are we doing about it?* *How will we know if it failed?*

A handy checklist is **STRIDE**: **S**poofing (pretending to be someone), **T**ampering (altering data), **R**epudiation (denying an action with no proof), **I**nformation disclosure (leaks), **D**enial of service, **E**levation of privilege. Walk each arrow in your architecture diagram and ask which of the six applies. A **trust boundary** is any line where data crosses from a less trusted to a more trusted zone (internet to gateway, gateway to service, service to database): every crossing needs authentication, validation and logging.

Two principles carry most of security design. **Defence in depth**: assume any single control can fail, and layer several (network rules, authentication, authorisation, validation, encryption, monitoring). **Least privilege**: the web server's database account cannot drop tables; the image resizer cannot read user passwords; an engineer's access expires.

{{fig defence-layers | Defence in depth. A request passes several independent controls; an attacker must defeat all of them, and each layer limits the damage if another fails.}}

## Authentication {#sec-authn}

**Authentication** establishes identity using something you **know** (password), **have** (phone, hardware key) or **are** (biometric). Use **multi-factor authentication (MFA)** for anything valuable: stolen passwords alone then do not suffice.

**Passwords must never be stored in plain text or with fast hashes.** Store a **salted, slow, memory-hard hash** (Argon2id, bcrypt or scrypt): a random per-user *salt* ensures identical passwords have different hashes and defeats precomputed tables; deliberate slowness makes guessing billions of passwords expensive. On login, hash the submitted password with the stored salt and compare in constant time. Add rate limiting and lockout or delay after failures (Chapter {ch:ch-entry}), check against lists of breached passwords, and never roll your own cryptography.

### Sessions and tokens

After login the server must recognise the user on later requests (HTTP is stateless, Chapter {ch:ch-network}). Two common designs:

- **Server-side session**: the server stores session data and gives the browser a random, unguessable **session id** in a cookie (flagged `HttpOnly`, `Secure`, and `SameSite`). Easy to revoke (delete the session) but needs a shared session store (Chapter {ch:ch-cache}).
- **Signed token (for example a JWT, JSON Web Token)**: the server signs a token containing the user id, roles and an expiry; any server can verify the signature without a lookup. Good for stateless services and service-to-service calls, but a token **cannot be revoked** before expiry unless you keep a deny-list, so use *short lifetimes* (minutes) with a longer-lived **refresh token** stored and checkable on the server. Never put secrets in a JWT (it is encoded, not encrypted), always verify the signature *and* the expiry, audience and issuer, and reject the `none` algorithm.

### OAuth 2.0 and OpenID Connect

Often users should log in through another provider, or an app should act on a user's behalf *without* getting their password. **OAuth 2.0** is a framework for **delegated authorisation**: the user grants an app limited access (a *scope*, such as "read your calendar") to resources on another service, and the app receives an **access token** instead of a password. **OpenID Connect (OIDC)** adds an **ID token** on top, so that OAuth can also be used for **login** ("Sign in with..."). The standard browser flow is the **authorization code flow with PKCE**.

{{fig oauth | Authorisation code flow with PKCE. The user authenticates at the identity provider, never at the app; the app receives a short-lived code and exchanges it, with proof that it started the flow, for tokens.}}

## Authorization {#sec-authz}

**Authentication answers "who are you?"; authorization answers "may you do this?"** Confusing them causes the most common serious vulnerability, **broken access control**: the user is logged in (authenticated) and then fetches `/orders/1234` for *someone else's* order (an **insecure direct object reference**, IDOR) because the server only checked that a session exists.

Rules:

- **Authorise on every request, on the server**, using the identity from the verified session or token, never from client-supplied fields (a `userId` parameter in the request body is untrusted).
- **Check the specific resource**: "does this user own order 1234?", not merely "is this user logged in?"
- **Deny by default**; allow explicitly.
- Use a clear model: **RBAC** (role-based: *admin*, *editor*, *viewer*), **ABAC** (attribute-based: "doctors may see records of patients in their ward during their shift") or **ACLs** (per-resource lists). Keep policy in one place (a library or policy service) rather than scattered across handlers.
- Apply least privilege to *services too*: each service has its own credentials and permissions; a compromised one cannot reach everything.

::: note
**Clarification: server-side validation is authoritative.** Validation in the browser (a disabled button, a form pattern) is only a convenience for honest users; an attacker bypasses it with a script. Every rule that matters (price, permissions, limits, field formats) must be **enforced again on the server**, using server-side data: never trust a price, role, user id, or "is_admin" flag sent by the client.
:::

## Injection and common web attacks {#sec-attacks}

**Injection** happens when untrusted input is *interpreted as code or commands*. The notebook's two rules, **sanitise user input** and **use parameterised queries**, address the most famous case, SQL injection.

```python
# VULNERABLE: input becomes part of the SQL text
db.execute("SELECT * FROM users WHERE email = '" + email + "'")
#   email = "x' OR '1'='1"   -> returns every user
#   email = "x'; DROP TABLE users; --"  -> destroys data

# SAFE: the query shape is fixed; input is only ever a value
db.execute("SELECT * FROM users WHERE email = %s", (email,))
```

Parameterised (prepared) queries send the SQL and the values separately, so the database never mistakes data for commands. The same principle applies to shell commands, LDAP, template engines and more: **never build an interpreter's input by concatenating untrusted strings.**

Table[attacks]: Common attacks and their defences.

| Attack | What happens | Defence |
|---|---|---|
| SQL / command injection | Input executed as code | Parameterised queries; avoid shell calls; least-privilege database account |
| Cross-site scripting (XSS) | Attacker's script runs in a victim's browser, stealing sessions or acting as them | Escape output for its context; Content Security Policy; `HttpOnly` cookies |
| Cross-site request forgery (CSRF) | A malicious site makes the victim's browser send an authenticated request | `SameSite` cookies; anti-CSRF tokens; require re-authentication for sensitive actions |
| Server-side request forgery (SSRF) | The server is tricked into calling internal addresses (such as cloud metadata) | Allow-list outbound destinations; block internal ranges; do not follow redirects blindly |
| Broken access control / IDOR | Access to other users' data | Authorise per resource, per request, on the server |
| Credential stuffing | Reused leaked passwords tried at scale | MFA, rate limiting, breached-password checks, bot detection |
| Denial of service (DoS, DDoS) | Resource exhaustion | CDN or scrubbing service, rate limiting, autoscaling, load shedding |
| Insecure deserialisation, unsafe file upload | Code execution or storage abuse | Validate and scan; never deserialise untrusted data with unsafe formats; store uploads outside the web root with generated names |
| Supply-chain compromise | Malicious dependency or build step | Pin and verify dependencies; scan; minimal base images; signed builds |

::: warning
**Common mistakes.** Rolling your own crypto or password storage. Logging secrets, tokens or personal data. Verbose error messages exposing stack traces and database details. Trusting the client for authorisation data. Leaving default credentials, public storage buckets and debug endpoints enabled. Disabling TLS verification "temporarily".
:::

## Encryption and key management {#sec-crypto}

**In transit**: use TLS (Chapter {ch:ch-network}) on *every* hop, including internal service-to-service links; for service identity, **mutual TLS (mTLS)** lets both sides prove who they are. **At rest**: encrypt disks, databases and backups (the notebook's second encryption rule), so a stolen disk or backup reveals nothing; for highly sensitive fields (card numbers, government ids) add **application-level encryption** so even database administrators cannot read them.

Encryption is only as strong as **key management**. Keep keys in a **key management service (KMS)** or hardware security module, *not* in code or config files; use **envelope encryption** (a data key encrypts the data; a master key in the KMS encrypts the data key) so master keys never leave the KMS and can be **rotated** without re-encrypting everything; give access by role and audit every use; plan for rotation and for compromise (how do you replace a leaked key quickly?).

**Secrets management.** Passwords, API keys and certificates belong in a **secrets manager** (cloud vault services, HashiCorp Vault, Kubernetes secrets with encryption), injected at runtime, **never committed to source control**. Prefer short-lived, automatically rotated credentials, scan repositories for accidental secrets, and revoke immediately if one leaks. Assume anything ever pushed to a repository is public.

## Abuse prevention {#sec-abuse}

Not all attackers break in; many simply *use* the service in unintended ways: spam signups, scraping, credential stuffing, fake reviews, free-tier farming. Defences are layered: **rate limits** per account, IP and device (Chapter {ch:ch-entry}); **CAPTCHA** or proof-of-work for suspicious flows; **bot detection** and anomaly scoring; **email and phone verification**; **quotas and cost caps**; **honeypots**; a **reporting and takedown** process for user-generated content; and **monitoring** for patterns (many accounts from one device). Balance friction against usability: apply stronger checks only when risk signals are high.

## Privacy by design {#sec-privacy}

**Privacy** concerns what personal data you collect, why, who sees it and how long you keep it. Regulations such as the GDPR (European Union), the CCPA (California) and India's DPDP Act impose duties; details vary by jurisdiction and change, so involve legal counsel for compliance. Engineering practices that make compliance feasible:

- **Data minimisation**: do not collect what you do not need; the safest data is data you never stored.
- **Purpose limitation and consent**: record why data was collected and what the user agreed to.
- **Classify data** (public, internal, confidential, regulated) and apply controls accordingly; know **where PII lives** (databases, logs, caches, analytics, backups, search indexes).
- **Retention limits**: delete or anonymise data when no longer needed, automatically.
- **User rights**: be able to *export* and *delete* a person's data on request. Deletion across replicas, caches, search indexes and backups is hard: design **data maps** early, use **per-user encryption keys** so deleting the key "crypto-shreds" all copies (including backups), and document how long backups retain data.
- **Pseudonymisation and anonymisation**: replace identifiers with tokens; aggregate data; remember that data thought anonymous can often be re-identified when combined with other data.
- **Keep PII out of logs and analytics**, or mask it.
- **Audit logs**: record who accessed or changed sensitive data and when, in append-only, tamper-evident storage separate from the application.

::: supplement
**Security in the design process.** Include security in design reviews (a threat model per feature), automate checks in the build pipeline (dependency scanning, static analysis, secret scanning, container image scanning), run regular penetration tests, keep a **vulnerability disclosure policy**, practise **incident response** (who decides, who communicates, how to contain, how to preserve evidence), and patch quickly: most breaches use known, already-fixed flaws.
:::

::: failure
**Failure modes.** Leaked credentials in a public repository; an expired or mis-issued certificate; broken access control exposing other users' data; a compromised dependency; session tokens stolen via XSS; an unprotected admin interface; backups unencrypted or accessible to everyone; keys stored beside the data they protect; log files containing passwords or card numbers; a successful DDoS exhausting capacity; insider misuse with no audit trail; encryption turned on but keys never rotated.
:::

::: misconception
- *"We use HTTPS, so we are secure."* TLS protects data in transit only; it does nothing against injection, broken access control or weak passwords.
- *"JWTs are encrypted."* They are signed, not encrypted; the contents are readable.
- *"Client-side validation is enough."* Attackers do not use your client.
- *"Security through obscurity (hidden URLs, secret formats) protects us."* It only delays attackers; assume the design is known.
- *"Hashing and encryption are the same."* Hashing is one-way (passwords); encryption is reversible with a key (data).
:::

::: interview
**Q1. Authentication versus authorization?**
Authentication verifies identity (who you are); authorization decides permissions (what you may do). A logged-in user must still be checked against the specific resource on every request.

**Q2. How do you store passwords?**
Never plain text or fast hashes; use a unique salt and a slow, memory-hard hash (Argon2id, bcrypt, scrypt); add MFA, rate limiting and breached-password checks.

**Q3. How do you prevent SQL injection?**
Parameterised queries (prepared statements), least-privilege database accounts, input validation; never concatenate input into SQL.

**Q4. Sessions or JWTs?**
Sessions: easy revocation, need a shared store. JWTs: stateless verification, hard to revoke; use short expiry plus refresh tokens. Choose by revocation needs and architecture.
:::

::: exercise
1. List three STRIDE threats for the paste service of Chapter {ch:ch-intro} and one control for each.
2. An endpoint `GET /invoices/{id}` returns any invoice to any logged-in user. Describe the vulnerability and the fix, in code or pseudocode.
3. Design secret handling for a service that needs a database password and a payment API key, covering storage, rotation and a leak response.
4. A user asks to be forgotten. List the places their data may live in the architecture of Chapter {ch:ch-intro} and a plan to delete it.

**Answers.**
1. Spoofing: attacker posts as another user, so require authentication and MFA. Information disclosure: private pastes guessable by sequential ids, so use long random identifiers and authorisation checks. Denial of service: mass paste creation, so use rate limits and size limits. (Others: tampering with content, so make pastes immutable; elevation, so least privilege.)
2. Broken access control (IDOR). Fix: `invoice = db.get(id); if invoice.owner_id != current_user.id and not current_user.is_admin: return 404`, deriving `current_user` from the verified session; return 404 rather than 403 to avoid confirming existence.
3. Store in a secrets manager; inject at start-up through the runtime environment or a mounted file; use short-lived database credentials or rotate at least quarterly; separate credentials per service; on a leak, revoke immediately, rotate, audit use, and search logs for abuse.
4. Primary database, replicas, caches, search index, object store, logs, analytics warehouse, backups, and third-party processors. Plan: data map; delete or anonymise in each store; purge caches; propagate by event; for backups, document retention or use per-user keys; confirm and log completion.
:::

::: summary
- Threat-model first; layer defences; apply least privilege.
- Authenticate with MFA and slow salted password hashes; use sessions or short-lived signed tokens; OAuth 2.0 plus OIDC for delegated access and login.
- Authorise on the server for every request and resource; validation on the server is authoritative.
- Prevent injection with parameterised queries; defend against XSS, CSRF, SSRF.
- Encrypt in transit and at rest; manage keys and secrets properly; plan for abuse; build privacy in (minimise, retain briefly, make deletion possible); keep audit logs.
:::

::: revision
- [ ] I can apply STRIDE to an architecture diagram.
- [ ] I can explain salted slow password hashing.
- [ ] I can explain the OAuth 2.0 code flow and PKCE.
- [ ] I can spot and fix an IDOR.
- [ ] I can explain envelope encryption and secrets management.
:::
