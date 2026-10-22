%derived Notebook chapter 4 (CDN, push and pull CDNs, load balancers, layer 4 and layer 7, reverse proxy, the comparison tables)
%added rate limiting, API gateways, health checking and graceful draining, global traffic management, and capacity worked examples
# The Entry Layer: CDN, Load Balancers and Proxies {#ch-entry}

::: objectives
After this chapter you can:

- explain what a content delivery network does, when to use push or pull, and how to control and invalidate its caches;
- describe load balancer algorithms, layer 4 versus layer 7 balancing, health checks and the SPOF problem of the balancer itself;
- explain what a reverse proxy does and how it differs from a forward proxy and a load balancer;
- explain an API gateway and implement a token-bucket rate limiter;
- size an entry layer for a given traffic estimate.
:::

::: prereq
Chapter {ch:ch-network} (DNS, TCP, TLS, HTTP) and Chapter {ch:ch-estimation} (traffic estimation).
:::

::: terms
Edge / point of presence (PoP)
: A CDN data centre located close to users.

Origin
: The real servers that hold the authoritative content.

Cache hit / miss
: The requested item was found (hit) or not found (miss) in a cache.

Health check
: A periodic probe that decides whether a server may receive traffic.

TLS termination
: Ending the encrypted connection at an intermediate server, which then forwards the request.

Rate limiting
: Rejecting or delaying requests beyond an allowed rate per client.
:::

## Why an entry layer {#sec-entrywhy}

Between users and application servers sits a layer of components that absorb, filter, spread and speed up traffic *before* it reaches code you wrote. Each does a job you would otherwise have to build into every application: answer static content from nearby ({sec:cdn}), spread load and hide failures ({sec:lb}), terminate encryption and compress ({sec:proxy}), and protect against abuse ({sec:ratelimit}). Putting these jobs at the edge keeps application servers simple and stateless.

## Content delivery networks {#cdn}

A **content delivery network (CDN)** is a globally distributed network of caching servers. A user's request for an image, script or video is answered by an edge server close to them instead of travelling to the origin across an ocean. This cuts latency (distance dominates: Chapter {ch:ch-estimation}), reduces load and bandwidth on the origin, and helps absorb traffic spikes and some attacks.

{{fig cdn-flow | A pull CDN. On the first request the edge misses and fetches from the origin, then stores the object. Later users near that edge get it directly until the object expires.}}

### Push and pull

**Pull CDN.** The CDN fetches content from your origin the first time someone asks, then caches it for a time to live. You change nothing in your upload process: you point URLs at the CDN. The first user in each region sees a slower request (a miss); popular content is soon cached everywhere. Cost: origin traffic on first requests and on expiry; risk of stale content until TTL ends.

**Push CDN.** *You* upload content to the CDN when it changes, and the CDN stores it until you replace or remove it. Nothing expires on its own, so there is no miss penalty and no unnecessary origin traffic, but you must manage uploads and storage, and a forgotten update leaves old content live.

Table[pushpull]: Push versus pull CDN.

| | Pull | Push |
|---|---|---|
| Who loads content | CDN, on first request | You, on change |
| Origin traffic | Misses and expiry | Only your uploads |
| Effort | Minimal | You manage uploads and removals |
| First request | Slower (miss) | Fast (already there) |
| Best for | Sites with much content that changes often or unpredictably | Small, rarely changing content: installers, firmware, big media |

### Controlling caches

The origin tells caches what to do with HTTP headers: `Cache-Control: max-age=86400` (cache for a day), `s-maxage` (a CDN-specific TTL), `no-store` (never cache; for private data), `private` (browser may cache, shared caches may not), and validators `ETag` and `Last-Modified` so a cache can ask "is my copy still current?" and receive `304 Not Modified` instead of the full body.

**Invalidation** is the hard part. Options: wait for the TTL; send a **purge** request (slow or costly at scale, and not instant everywhere); or best, use **versioned, content-hashed URLs** (`app.3f9c2a.js`). A changed file gets a new URL, so old copies are simply never requested again, and the files can be cached for a year safely. Only the HTML that references them needs a short TTL.

::: warning
**Common mistakes.** Caching personalised or private responses at the CDN (leaking one user's page to another; always vary or exclude by `Authorization` or cookies). Short TTLs on static files that never change. No cache key discipline: query strings that differ per user make every request a miss. Forgetting that a CDN is a cache: stale content is the price of speed.
:::

## Load balancers {#lb}

A **load balancer** receives requests and distributes them across a pool of servers. It provides **capacity** (many servers share traffic), **availability** (it stops sending traffic to failed servers), and **flexibility** (servers can be added, removed or upgraded without clients noticing).

{{fig lb-pool | A load balancer spreads requests over a pool. Health checks (dashed) remove failed servers from rotation; the balancer is itself duplicated to avoid being a single point of failure.}}

### Algorithms

Table[lbalgo]: Load-balancing algorithms.

| Algorithm | How it chooses | Good when | Watch out |
|---|---|---|---|
| Round robin | Next server in turn | Similar servers, similar requests | Ignores current load |
| Weighted round robin | Round robin with weights | Servers of different sizes | Weights must be maintained |
| Least connections | Server with fewest open connections | Long or uneven requests | Needs connection tracking |
| Least response time | Fastest recent responses | Heterogeneous backends | Measurement noise |
| IP / key hash | Hash of client IP or key | Same client to the same server (cache locality) | Skewed keys; reshuffles when pool changes (consistent hashing helps) |
| Random of two | Pick two at random, take the less loaded | Large pools, little coordination | None serious; surprisingly effective |

### Layer 4 and layer 7

A **layer 4 balancer** works on transport information (IP address and port), forwarding TCP or UDP streams without reading them. It is very fast and protocol-agnostic. A **layer 7 balancer** understands HTTP: it can route by URL path or header (`/api` to one pool, `/images` to another), terminate TLS, compress, add or remove headers, and retry on another server. It is more flexible and more expensive per request.

Table[l4l7]: Layer 4 versus layer 7 balancing.

| | Layer 4 | Layer 7 |
|---|---|---|
| Looks at | IP, port | Full HTTP request |
| Routing by path or header | No | Yes |
| TLS termination | Passes through (or terminates in some products) | Typically terminates |
| Throughput per machine | Higher | Lower |
| Typical use | Front door for huge traffic, non-HTTP protocols | Web applications, microservice routing |

### Health checks, stickiness, draining

**Health checks** probe each server (a TCP connect, or an HTTP `GET /healthz`). After several consecutive failures the balancer stops using the server; after successes it returns. A good health check tests the server's *ability to serve* (for example, can it reach its database?) but not so deeply that one shared dependency failing marks *every* server unhealthy and takes the whole site down. **Session persistence ("sticky sessions")** pins a client to one server, a workaround for servers that keep state in memory (Chapter {ch:ch-intro}); it makes load uneven and loses sessions when the server dies, so prefer stateless servers. **Connection draining** lets in-flight requests finish before a server is removed during a deployment.

### The balancer as a SPOF

A single balancer is a single point of failure. Typical remedies: **active-passive** pairs (a standby takes over the same address if the active fails), **active-active** pairs or clusters (both serve traffic), or **DNS** and **anycast** routing to several balancers in different locations. Cloud balancers are already distributed and managed for you; the trade-off is cost and less control.

## Reverse proxies and gateways {#proxy}

A **forward proxy** sits in front of *clients* (a corporate proxy that filters outbound traffic). A **reverse proxy** sits in front of *servers*: clients talk to it as if it were the server, and it forwards requests to the real servers. Examples are NGINX, HAProxy and Envoy.

{{fig reverse-proxy | A reverse proxy is the public face of the servers. It terminates TLS, compresses, caches, and routes by path to different back-end services, which are never exposed to the internet.}}

Benefits: **security** (back ends have no public addresses; it can block bad requests and hide topology), **TLS termination** (certificates and encryption work in one place), **compression and caching** of responses, **static file serving**, **request routing** and **buffering slow clients** so application servers are not tied up waiting for them. Costs: another hop (a little latency), another component to operate, and it can become a bottleneck or SPOF if not replicated.

::: note
**Load balancer versus reverse proxy.** The terms overlap. A load balancer's defining job is *spreading load across several servers*; a reverse proxy's defining job is *standing in for the servers* (security, TLS, caching, routing), and it is useful even with a single back end. Many products do both: NGINX is commonly used as a reverse proxy *and* a layer 7 balancer. In diagrams, name the *role* each box plays.
:::

An **API gateway** is a reverse proxy specialised for APIs. It adds authentication, **rate limiting**, request and response transformation, API-key management, versioned routing, and usage metrics, at one entry point for many back-end services. It centralises cross-cutting policy but must be kept thin; business logic placed in the gateway becomes a bottleneck and a hidden monolith.

## Rate limiting {#ratelimit}

**Rate limiting** protects a service from overload and abuse by capping how many requests a client may make in a time window; excess requests receive `429 Too Many Requests` (with `Retry-After`). It also enforces fairness and billing tiers.

The **token bucket** algorithm is the usual choice. A bucket holds up to *B* tokens and refills at rate *r* tokens per second. Each request takes one token; if none is available the request is rejected. The result: sustained rate *r*, with bursts up to *B* allowed.

{{fig token-bucket | Token bucket: tokens drip in at a constant rate up to a maximum; each request consumes one. A full bucket permits a burst; an empty bucket rejects.}}

```python
class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate, self.capacity = rate, capacity      # tokens/sec, max tokens
        self.tokens, self.last = capacity, now()
    def allow(self):
        t = now()
        self.tokens = min(self.capacity, self.tokens + (t - self.last) * self.rate)
        self.last = t
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

Alternatives: **fixed window** counters (simple, but allow double bursts at window edges), **sliding window log** (exact, memory-heavy) and **sliding window counter** (an approximation using two adjacent windows). In a distributed deployment the counters live in a shared fast store (for example a distributed cache with atomic increment and expiry); the trade-off is an extra network call per request versus the accuracy of limits when each server counts independently.

## Putting it together: sizing the entry layer {#sec-entrysize}

::: worked
**Sizing for the messaging example of Chapter {ch:ch-estimation}.** Peak: 100,000 reads per second and 10,000 writes per second, response 1 KB, of which perhaps 70% could be served by a CDN or edge cache if static.

- Traffic reaching the origin: 30% × 110,000 ≈ 33,000 requests per second; outbound ≈ 33 MB/s ≈ 264 Mbps.
- If one application server handles about 2,000 requests per second comfortably (assumed, to be measured), we need 33,000 / 2,000 ≈ 17 servers; with headroom for peak and one failed zone (run at ≤ 60% load, tolerate losing one of three zones), plan about 17 / 0.6 × 1.5 ≈ 43, rounded to about 45 servers across three zones.
- Two layer-4 balancers (active-active) comfortably handle this traffic; a layer-7 tier or gateway adds routing and rate limiting.
- The CDN absorbs 77,000 requests per second that never touch the origin: that is where most of the saving comes from.
:::

::: failure
**Failure modes.** CDN serving stale or wrong content after a bad deployment (versioned URLs and purge procedures help); thundering herd on the origin when a popular object expires everywhere at once (*request collapsing* and stale-while-revalidate headers help); a health check that is too sensitive flapping servers in and out; a balancer misconfigured to send everything to one server; the gateway becoming the bottleneck; rate limiters failing closed and rejecting all traffic when their counter store is down (decide deliberately whether to fail open or closed); sticky sessions pinning load to one overloaded server.
:::

::: misconception
- *"A CDN is only for images."* It can cache API responses, accelerate dynamic requests through optimised routes, terminate TLS near users, and absorb attacks.
- *"Round robin balances load."* It balances request *counts*; if requests differ widely in cost, load is still uneven.
- *"A load balancer makes the system highly available."* Only if the balancer is itself redundant and servers do not share a hidden SPOF.
- *"Rate limiting is only for security."* It also protects capacity and enforces fairness.
:::

::: interview
**Q1. Push versus pull CDN?**
Pull fetches on demand and caches with a TTL (easy, first request is slow, may be stale); push has you upload content (no misses or surprise origin traffic, more management). Use pull for most sites, push for small, rarely changing, large files.

**Q2. Layer 4 versus layer 7 load balancing?**
Layer 4 forwards by IP and port: fast, protocol-agnostic. Layer 7 reads HTTP: routes by path or header, terminates TLS, retries; slower but flexible.

**Q3. How do you avoid the load balancer being a single point of failure?**
Run several, active-active or active-passive, behind DNS or anycast, or use a managed cloud balancer; test failover.

**Q4. Design a rate limiter.**
Token bucket per client key stored in a shared fast store with atomic operations; return 429 and `Retry-After`; decide fail-open or fail-closed; apply at the gateway; consider per-user, per-IP and per-endpoint limits.
:::

::: exercise
1. A pull CDN has a 90% hit ratio. Origin capacity is 2,000 requests per second. What total request rate can the site serve?
2. A bucket has capacity 20 and refill rate 5 tokens/s. A client sends 30 requests at once at time 0, then one per 100 ms. How many of the first 30 are accepted? What sustained rate is allowed?
3. Choose a load-balancing algorithm for (a) identical stateless web servers, (b) a pool where requests vary from 10 ms to 30 s, (c) a cache tier where the same key should hit the same node.
4. Why can a health check that calls the database cause an outage?

**Answers.**
1. Only 10% of requests miss: total ≈ 2,000 / 0.10 = 20,000 requests per second (if the CDN itself is unconstrained).
2. 20 accepted (the full bucket), 10 rejected. Sustained rate 5 per second (1 per 200 ms), so the client's one-per-100 ms stream (10/s) would see about half rejected.
3. (a) Round robin or random-of-two; (b) least connections; (c) hash by key, preferably consistent hashing.
4. If the database slows or fails, every server's health check fails at once, so the balancer removes all servers and the service goes fully down even though the web servers were healthy; shallow checks or "fail static" behaviour avoid this.
:::

::: summary
- The entry layer handles caching, spreading, filtering and protecting traffic before application code.
- CDNs cut latency and origin load; pull is easy, push gives control; use versioned URLs to avoid invalidation pain.
- Load balancers spread load and hide failures; choose the algorithm by request shape; layer 7 is flexible, layer 4 is fast; replicate the balancer.
- Reverse proxies and gateways centralise TLS, caching, routing, authentication and rate limiting.
- Token buckets allow bursts at a bounded sustained rate; decide fail-open or fail-closed.
:::

::: revision
- [ ] I can explain a cache hit and miss at the CDN and how to purge or version.
- [ ] I can name four balancing algorithms and when each fits.
- [ ] I can explain L4 versus L7 and the balancer SPOF.
- [ ] I can write a token bucket.
:::

::: supplement
**Further reading.** The HTTP caching specification (RFC 9111); Google's "The Site Reliability Workbook" chapters on load balancing; Mitzenmacher's analysis of "the power of two choices"; documentation for NGINX, HAProxy and Envoy for concrete configuration.
:::
