%part Part II | Networking and the Entry Layer | How requests find a server, travel to it, and are spread across many servers.
%derived Notebook chapter 3 (layers in one minute, HTTP, TCP and UDP) and the DNS section of chapter 4
%added TLS, QUIC and HTTP/3, the connection-setup latency budget, and the complete request lifecycle
# Networking and the Request Lifecycle {#ch-network}

::: objectives
After this chapter you can:

- describe the layers a message passes through and name a protocol at each layer;
- trace a DNS lookup from the browser to an authoritative server and explain TTLs and caching;
- explain the TCP handshake, reliability, flow control and congestion control, and when UDP is the better choice;
- explain what TLS adds and what it costs in round trips;
- distinguish HTTP/1.1, HTTP/2 and HTTP/3, including that HTTP/3 runs over QUIC on UDP while HTTP/2 normally runs over TCP;
- count the round trips of a cold request and predict its minimum latency.
:::

::: prereq
Chapter {ch:ch-intro} (request path, latency) and Chapter {ch:ch-estimation} (latency numbers).
:::

::: terms
IP address
: A number identifying a network interface, for example `203.0.113.7` (IPv4) or `2001:db8::7` (IPv6).

Port
: A number (0 to 65535) selecting a program on a machine; HTTPS conventionally uses 443.

Packet
: A small chunk of data, with addressing information, that is routed independently across the network.

Protocol
: An agreed set of rules for exchanging messages.

Round trip time (RTT)
: The time for a message to reach the other side and a reply to return.

Domain Name System (DNS)
: The distributed directory that maps names such as `example.com` to IP addresses.

Transmission Control Protocol (TCP) / User Datagram Protocol (UDP)
: The two main transport protocols: TCP provides a reliable ordered stream; UDP sends independent datagrams with no guarantees.

Transport Layer Security (TLS)
: The protocol that encrypts and authenticates a connection (the "S" in HTTPS).
:::

## Layers in one minute {#sec-layers}

Networks are built in layers, each using the layer below and hiding its details. You do not need every layer, but you need to know which one a problem belongs to.

Table[layers]: The layers we use and example protocols.

| Layer | Job | Examples | Addressed by |
|---|---|---|---|
| Application | What the two programs say to each other | HTTP, DNS, SMTP (email), gRPC | URL, name |
| Transport | Delivery between programs; reliability | TCP, UDP, QUIC | Port |
| Network (internet) | Routing packets between machines | IP | IP address |
| Link / physical | Moving bits across one hop | Ethernet, Wi-Fi, fibre | MAC address |

As a request is sent, each layer wraps the data from the layer above in its own header (**encapsulation**); the receiver unwraps in reverse order ({fig:encap}). Load balancers are often described as "layer 4" (they look at IP addresses and ports, treating traffic as opaque) or "layer 7" (they read HTTP and can route by URL or header); see Chapter {ch:ch-entry}.

{{fig encap | Encapsulation. The HTTP request is wrapped in a TCP segment (adding ports and sequencing), which is wrapped in an IP packet (adding addresses), which is carried in a link-layer frame.}}

## DNS: names to addresses {#dns}

People remember names; routers need numbers. **DNS** is a worldwide, hierarchical, cached directory. A name is read right to left: in `www.example.com`, the dot at the end is the **root**, `com` is the **top-level domain** (TLD), `example` is the domain registered by a company, and `www` is a host chosen by that company.

Three kinds of servers cooperate:

- A **recursive resolver** (run by your internet provider, your company, or a public service) does the legwork for you and caches results.
- **Root and TLD servers** do not know the answer but know who does.
- The **authoritative name server** holds the real records for a domain and gives the final answer.

{{fig dns-resolution | Resolving www.example.com on a cold cache. The resolver asks the root, then the TLD servers, then the authoritative server; each step narrows the search. The answer is cached for its time to live.}}

The steps in {fig:dns-resolution}: the browser asks its local resolver; the resolver, with nothing cached, asks a root server, which refers it to the servers for `.com`; those refer it to the authoritative servers for `example.com`; and those return the address. The resolver returns the answer and *caches* it. Typically a lookup that hits a warm cache takes about a millisecond; a cold lookup may take tens to hundreds of milliseconds.

### Record types and TTL

Table[dnsrec]: Common DNS record types.

| Type | Meaning | Example |
|---|---|---|
| A | Name to IPv4 address | `www  A  203.0.113.7` |
| AAAA | Name to IPv6 address | `www  AAAA  2001:db8::7` |
| CNAME | Alias to another name | `static  CNAME  cdn.provider.net` |
| NS | Which servers are authoritative | `example.com  NS  ns1.provider.net` |
| MX | Where email goes | `example.com  MX  10 mail.example.com` |
| TXT | Free text (verification, email policy) | `"v=spf1 ..."` |

Every answer carries a **time to live** (TTL), the number of seconds caches may keep it. A long TTL (hours) reduces load and speeds lookups; a short TTL (seconds or minutes) lets you move traffic quickly. The trade-off is explicit: *caching makes DNS fast, but changes propagate slowly*. Before a planned migration, lower the TTL a day ahead.

### Routing tricks DNS can do

Because the authoritative server chooses the answer, it can steer traffic: **round robin** (rotate among several addresses), **weighted** (send 10% to a new data centre), **latency-based** (answer with the region fastest for the resolver) and **geographic** (answer by user country, useful for data-residency rules). It can also withhold unhealthy addresses if a health checker tells it which servers are down.

::: warning
**Common mistakes.** Assuming DNS failover is instant: clients and resolvers ignore low TTLs sometimes, so recovery can take minutes. Running your own authoritative DNS without redundancy (a single DNS provider outage can take your whole site offline even though your servers are healthy; many organisations use a managed, anycast DNS service or two providers). Putting a CNAME at the zone apex, which standard DNS disallows.
:::

## TCP: a reliable stream {#sec-tcp}

IP delivers packets on a best-effort basis: they can be lost, duplicated, reordered or delayed. **TCP** builds a dependable ordered byte stream on top. It does this with:

- a **handshake** to establish a connection;
- **sequence numbers** so the receiver can reorder data and detect missing pieces;
- **acknowledgements** and **retransmission** of anything unacknowledged;
- **checksums** to detect corruption;
- **flow control**, which stops a fast sender from overwhelming a slow receiver (the receiver advertises how much more it can accept);
- **congestion control**, which slows the sender when the network seems overloaded (packet loss is taken as the signal), starting slowly and speeding up (*slow start*).

{{fig tcp-handshake | The TCP three-way handshake, then data. The connection costs one round trip before the first byte of application data can be sent.}}

The handshake ({fig:tcp-handshake}) is SYN (client says hello and proposes a starting sequence number), SYN-ACK (server acknowledges and proposes its own), ACK (client acknowledges). After that, both sides can send data. The setup costs **one RTT** before the request can leave. That is why servers and clients **reuse connections** (keep-alive, connection pools) instead of opening a new one for each request, and why a new connection starts slowly because of slow start. A TCP stream also suffers **head-of-line blocking**: if one packet is lost, later data already received must wait until the missing piece is retransmitted.

## UDP and QUIC {#sec-udp}

**UDP** sends independent datagrams with just a port and a checksum: no handshake, no ordering, no retransmission, no congestion control. It is therefore fast to start and light, but the application must cope with loss and reordering itself.

Table[tcpudp]: TCP versus UDP.

| | TCP | UDP |
|---|---|---|
| Connection | Handshake required, stateful | None |
| Delivery | Reliable, ordered | Best effort; loss and reordering possible |
| Overhead | Higher (headers, state, retransmission) | Lower |
| Speed to first byte | One extra RTT | Immediate |
| Good for | Web pages, APIs, file transfer, email, databases | Live voice and video, games, DNS queries, telemetry |

Use TCP when you need every byte, in order (a bank transfer, a web page). Use UDP when stale data is worthless and speed matters more than completeness (a video call: a lost frame is better skipped than waited for). UDP also supports broadcast and multicast, useful for service discovery on a local network.

**QUIC** (standardised in 2021) is a modern transport protocol built *on top of UDP*. It reimplements reliability, ordering, congestion control and encryption in user space, as many independent streams over one connection. Because streams are independent, one lost packet delays only its own stream, removing TCP's head-of-line blocking. It also combines the transport and TLS handshakes, saving round trips, and a connection can survive a client changing networks (such as moving from Wi-Fi to mobile data), because it is identified by a connection ID rather than by addresses.

## TLS: encryption and identity {#sec-tls}

Plain HTTP can be read and altered by anyone on the path. **TLS** provides three properties: **confidentiality** (outsiders cannot read the data), **integrity** (tampering is detected) and **authentication** (the server proves it is who it claims to be).

The server presents a **certificate**: a document binding its name to a public key, signed by a **certificate authority** (CA) that browsers trust. In the handshake the client verifies the certificate chain, the client and server agree on session keys using public-key cryptography (a key exchange), and the rest of the connection is encrypted with fast symmetric keys. With TLS 1.3 the handshake takes **one RTT** (zero for a resumed connection in some cases, with replay-attack caveats), against two in TLS 1.2.

::: note
**Clarification on terminology.** People say "SSL" but the old SSL protocols are obsolete; what is used today is TLS. "SSL termination" in load-balancer language means ending the TLS connection at the balancer, which then forwards decrypted (or re-encrypted) traffic to the servers behind it; see Chapter {ch:ch-entry}.
:::

## HTTP: the language of the web {#sec-http}

HTTP (HyperText Transfer Protocol) is the application protocol of the web and most public APIs. It is **request/response** and stateless: each request carries everything the server needs, and the server remembers nothing between them (state, such as a login, is carried explicitly by cookies or tokens).

A request has a **method**, a **path** (and query), **headers** and an optional **body**; a response has a **status code**, headers and a body.

```http
GET /users/42 HTTP/1.1
Host: api.example.com
Accept: application/json
Authorization: Bearer <token>

HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: max-age=60

{"id": 42, "name": "Asha"}
```

Table[httpmethods]: Common methods. *Safe* methods do not change server state; *idempotent* methods have the same effect whether sent once or many times.

| Method | Meaning | Safe | Idempotent |
|---|---|---|---|
| GET | Read a resource | Yes | Yes |
| HEAD | Like GET without the body | Yes | Yes |
| POST | Create a resource or trigger processing | No | **No** |
| PUT | Create or replace a resource | No | Yes |
| PATCH | Partially update | No | Not guaranteed |
| DELETE | Remove | No | Yes |

Table[httpstatus]: Status code families.

| Family | Meaning | Examples |
|---|---|---|
| 1xx | Informational | 101 Switching Protocols |
| 2xx | Success | 200 OK, 201 Created, 204 No Content |
| 3xx | Redirect | 301 Moved Permanently, 302 Found, 304 Not Modified |
| 4xx | Client error | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 429 Too Many Requests |
| 5xx | Server error | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout |

Idempotency matters because the network is unreliable: if a client sends a request and the connection drops before the reply arrives, it does not know whether the server acted. Retrying a PUT or DELETE is safe; retrying a POST may duplicate the action unless the API provides an *idempotency key* (Chapter {ch:ch-api}).

### HTTP versions

Table[httpversions]: How HTTP versions differ.

| Version | Transport | Key idea | Limitation |
|---|---|---|---|
| HTTP/1.1 | TCP | Keep-alive reuses connections; text format | One request at a time per connection; browsers open several connections |
| HTTP/2 | TCP (normally, with TLS) | Binary framing; many requests multiplexed on one connection; header compression | TCP head-of-line blocking: one lost packet stalls all streams |
| HTTP/3 | **QUIC over UDP** | Same ideas as HTTP/2 over independent QUIC streams | UDP may be blocked or throttled on some networks; clients fall back to HTTP/2 |

::: note
**Clarification.** The notebook pairs HTTP with TCP, which is accurate for HTTP/1.1 and HTTP/2. HTTP/3 does not use TCP at all: it uses QUIC, which runs over UDP. This does not make HTTP/3 unreliable; QUIC supplies reliability itself. The practical rule: HTTP/1.1 and HTTP/2 need a TCP (and usually TLS) handshake; HTTP/3 needs one combined QUIC handshake.
:::

## The full lifecycle of a cold request {#sec-lifecycle}

Putting it together: what must happen before the first byte of a web page arrives at a user who has never visited the site?

{{fig lifecycle | Round trips of a first request to https://www.example.com over HTTP/2 with TLS 1.3. Each step must complete before the next begins, so latency adds up.}}

::: worked
**Minimum latency of a cold request.** Suppose the user is 40 ms RTT from the server, the DNS resolver is 10 ms away, and the authoritative lookup is cached at the resolver.

- DNS (cached at resolver): 1 RTT to resolver = 10 ms.
- TCP handshake: 1 RTT = 40 ms.
- TLS 1.3 handshake: 1 RTT = 40 ms.
- HTTP request and first byte of response: 1 RTT plus server work = 40 ms + say 20 ms = 60 ms.
- **Total ≈ 150 ms** before the first byte, of which only 20 ms is the server doing real work.

If the server is on another continent (RTT 150 ms) the same sequence costs about 10 + 150 + 150 + 170 = 480 ms. Remedies follow directly: terminate connections near the user (a CDN or edge proxy), reuse connections, use TLS 1.3 and session resumption, and use HTTP/3 where possible so that transport and encryption share one handshake. Without any change to application code the user sees roughly half the delay.
:::

::: failure
**Failure modes.** DNS outages or poisoned caches; expired TLS certificates (a very common cause of outages, prevented by automated renewal and monitoring); TCP connection exhaustion when many short-lived connections leave the server with thousands in a waiting state; packet loss triggering retransmission delays and congestion backoff; a firewall blocking UDP so HTTP/3 must fall back; MTU (maximum packet size) mismatches causing mysterious hangs for large responses.
:::

::: misconception
- *"HTTPS is slow."* The handshake costs round trips, but connection reuse and TLS 1.3 make the steady-state cost small.
- *"UDP is unreliable so protocols built on it are unreliable."* QUIC is reliable; reliability just moves into the protocol above UDP.
- *"DNS changes are instant."* Caches keep old answers until their TTL expires, and some ignore low TTLs.
- *"HTTP keeps a session."* HTTP is stateless; sessions are built from cookies or tokens.
:::

::: interview
**Q1. What happens when you type a URL and press Enter?**
Browser cache check; DNS resolution (resolver, root, TLD, authoritative); TCP (or QUIC) connection; TLS handshake; HTTP request; server processing, possibly via CDN, load balancer and cache; response; the browser parses, requests sub-resources, renders. Mention connection reuse and caching for extra credit.

**Q2. TCP versus UDP, and when would you choose each?**
TCP: reliable, ordered, connection-based; use for correctness-critical transfers. UDP: no guarantees, low overhead; use for real-time media, games, DNS, or when the application adds its own recovery.

**Q3. How does HTTP/3 differ from HTTP/2?**
HTTP/3 runs over QUIC on UDP rather than TCP: independent streams avoid head-of-line blocking, the transport and TLS handshakes are combined, and connections survive network changes.

**Q4. Why is a POST not safe to retry blindly?**
It may create a second resource; use an idempotency key so the server recognises the repeated request.
:::

::: exercise
1. A user is 80 ms RTT from the server. Estimate time to first byte for a brand-new HTTPS connection (HTTP/2, TLS 1.3), ignoring DNS and server work. How much does reusing the connection save?
2. A DNS record has a TTL of 86,400 s. You must move to a new IP address in one hour. What should you have done earlier?
3. Name one case each for choosing TCP, UDP and HTTP/3.
4. Explain how head-of-line blocking can make an HTTP/2 page load slow on a lossy network.

**Answers.**
1. TCP 80 ms + TLS 80 ms + HTTP 80 ms = 240 ms. Reusing the connection leaves only the HTTP round trip: 80 ms, saving 160 ms.
2. Lower the TTL to minutes at least a day beforehand (longer than the old TTL), then switch, then raise the TTL again.
3. TCP: file or database transfer; UDP: live video call or DNS query; HTTP/3: a mobile app on varying networks that benefits from fast setup and connection migration.
4. HTTP/2 multiplexes many streams over one TCP connection; a lost packet stalls all later data on that connection until it is retransmitted, so every stream waits even if their own data arrived.
:::

::: summary
- Layers hide detail: application (HTTP, DNS), transport (TCP, UDP, QUIC), network (IP), link.
- DNS is a cached hierarchy; TTL balances speed against agility; DNS can steer traffic.
- TCP gives reliable ordered streams at the cost of handshakes, head-of-line blocking and slow start; UDP trades guarantees for speed; QUIC rebuilds reliability over UDP.
- TLS adds confidentiality, integrity and authentication for one extra round trip (TLS 1.3).
- HTTP is stateless request/response; methods differ in safety and idempotency; HTTP/3 uses QUIC over UDP.
- Cold-request latency is mostly round trips: reduce them with edge termination, reuse and modern protocols.
:::

::: revision
- [ ] I can trace a DNS lookup and say what the TTL does.
- [ ] I can draw the TCP handshake and list TCP's guarantees.
- [ ] I can say which HTTP version uses which transport.
- [ ] I can count round trips for a cold request.
- [ ] I can say which HTTP methods are idempotent.
:::

::: supplement
**Further reading.** IETF RFC 9000 (QUIC) and RFC 9114 (HTTP/3), RFC 8446 (TLS 1.3), RFC 9110 (HTTP semantics); Ilya Grigorik, *High Performance Browser Networking* (free online).
:::
