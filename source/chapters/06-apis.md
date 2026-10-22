%derived Notebook chapter 3 (RPC and REST sections, the RPC-versus-REST operations table) and the API sketches inside the design problems
%added idempotency keys, pagination, versioning, error design, contracts and compatibility, webhooks versus polling
# APIs: RPC, REST and Contracts {#ch-api}

::: objectives
After this chapter you can:

- explain what an API is and why it is a *contract* between teams;
- compare RPC and REST, and choose between them for public and internal interfaces;
- design resource-oriented endpoints, status codes and error responses;
- implement safe retries with idempotency keys;
- page through large result sets with offset and cursor pagination and explain the trade-off;
- evolve an API without breaking existing clients.
:::

::: prereq
Chapter {ch:ch-network} (HTTP methods, status codes, idempotency).
:::

::: terms
API (application programming interface)
: The defined way one program asks another to do something.

Endpoint
: One addressable operation or resource of an API, for example `POST /pastes`.

RPC (remote procedure call)
: A style where the client calls a named action on a server as if it were a local function.

REST (representational state transfer)
: A style where clients operate on *resources*, identified by URLs, using standard HTTP methods.

Idempotent
: Doing it many times has the same effect as doing it once.

Idempotency key
: A unique value the client attaches to a request so the server can recognise and ignore duplicates.

Contract
: The agreed shape of requests, responses and behaviour that clients depend on.
:::

## Why APIs are contracts {#sec-contract}

Every boundary in a system, between a browser and a server, between two internal services, between your company and a partner, is an API. Once other programs depend on it, an API stops being an implementation detail and becomes a **contract**. Changing it carelessly breaks code you cannot see or redeploy. So API design is partly the design of *what can change later without breaking anyone*.

Two ideas shape most API decisions: the **style** (action-oriented RPC or resource-oriented REST) and the **failure behaviour** (what happens when a request is retried, partially fails, or arrives twice).

## RPC {#sec-rpc}

In **Remote Procedure Call** the client calls a named action with parameters, and the framework turns it into a network message. The call looks like a local function call, which is both its appeal and its danger: a local call does not fail with a timeout, but a remote one does, and the caller cannot always know whether the remote side ran it.

```text
POST /rpc/getUser           {"userId": 42}
POST /rpc/addItemToUserList {"userId": 42, "item": "book"}
```

Modern RPC frameworks (gRPC, Thrift, Avro) define the contract in a schema file, generate client and server code in many languages, and encode messages in a compact binary format over HTTP/2. They are fast, strongly typed and well suited to **internal** service-to-service calls where you control both ends.

{{fig rpc-stack | How an RPC call crosses the network. The client calls a generated stub, which marshals the arguments into bytes; the server skeleton unmarshals them and calls the real function. The reply travels back the same way.}}

**Strengths:** compact and fast, strict schemas, generated clients, streaming support. **Weaknesses:** clients are tightly coupled to the server's operations (a new operation means a new client release); binary formats are harder to debug by hand; browsers and third parties cannot call them as easily; caching at the HTTP layer is difficult because everything is typically a POST.

## REST {#sec-rest}

**REST** treats the server as a collection of **resources**: nouns such as users, orders and pastes, each with a URL. Clients use standard HTTP methods to operate on them, and the server is **stateless** between requests. Responses are *representations* of a resource, commonly JSON, and often contain links to related resources (this last property, called HATEOAS, is rarely fully implemented).

Table[restrpc]: The same operations expressed in RPC and REST (from the notebook, extended).

| Operation | RPC style | REST style |
|---|---|---|
| Sign up | `POST /signup` | `POST /persons` |
| Resign | `POST /resign` with `{"personid": 1234}` | `DELETE /persons/1234` |
| Read a person | `GET /readPerson?personid=1234` | `GET /persons/1234` |
| Read a person's items | `GET /readUsersItemsList?personid=1234` | `GET /persons/1234/items` |
| Add an item | `POST /addItemToUsersItemsList` | `POST /persons/1234/items` |
| Update an item | `POST /modifyItem` | `PUT /persons/1234/items/456` |
| Delete an item | `POST /removeItem` | `DELETE /persons/1234/items/456` |

REST rules of thumb: use **nouns, plural, hierarchical** URLs; let the **method** express the action; return the right **status code**; make `GET` safe and cacheable; make `PUT` and `DELETE` idempotent; and keep servers stateless so any instance can answer.

**Strengths:** easy to understand and debug (curl, a browser), works with HTTP caching and proxies, natural fit for public APIs and web clients. **Weaknesses:** can need several round trips to assemble one screen (the "chatty API" problem, which gateways or query-style APIs such as GraphQL address); not every action maps to a noun ("send the password-reset email"); versioning needs discipline; text formats are larger than binary.

::: warning
**Common mistakes.** Using GET for actions that change state (crawlers and prefetchers will trigger them). Returning 200 with an error message in the body, which breaks generic clients and monitoring. Exposing database identifiers and internal structure directly as the public contract, so every schema change breaks clients.
:::

Table[restvsrpc]: Choosing between RPC and REST.

| Situation | Prefer | Why |
|---|---|---|
| Public or third-party API | REST (JSON over HTTP) | Universal tooling, cacheable, human-readable |
| Internal calls between your own services | RPC (e.g. gRPC) | Speed, schemas, generated code |
| Mobile app wanting one call per screen | REST with aggregation, or a query-style API | Fewer round trips |
| Streaming or very high call volume | RPC with streaming | Efficient framing |

## Designing endpoints, errors and status codes {#sec-design}

A well-designed endpoint tells a client three things: what to send, what it will get, and what to do when something fails.

::: worked
**A paste API.** Suppose we build the text-sharing service from {ch:ch-intro}.

```http
POST /v1/pastes
Content-Type: application/json
Idempotency-Key: 6f1c0b52-...

{"content": "hello world", "expires_in_seconds": 86400}

HTTP/1.1 201 Created
Location: /v1/pastes/7Hq2Zx
Content-Type: application/json

{"id": "7Hq2Zx", "url": "https://paste.example/7Hq2Zx",
 "created_at": "2026-10-12T09:30:00Z", "expires_at": "2026-10-13T09:30:00Z"}
```

```http
GET /v1/pastes/7Hq2Zx          ->  200 OK  (or 404 Not Found, or 410 Gone if expired)
DELETE /v1/pastes/7Hq2Zx       ->  204 No Content  (idempotent: second call may return 404 or 204)
```

Observe: the version is in the path (`/v1`); the create call returns **201** with a `Location` header; an expired paste returns **410 Gone**, distinguishing "never existed" from "existed and was removed"; and the create call accepts an idempotency key (next section).
:::

**Error responses** should be consistent and machine-readable: a stable error *code* clients can switch on, a human message, and where relevant a field name and a request identifier for support.

```json
{"error": {"code": "paste_too_large", "message": "Content exceeds 512 KB.",
           "field": "content", "request_id": "req_91f3"}}
```

Choose status codes carefully. **400** for malformed requests, **401** for missing or invalid credentials (authentication), **403** for valid credentials without permission (authorization), **404** for unknown resources, **409** for conflicts such as a version mismatch, **422** for well-formed but semantically invalid input, **429** for rate limiting (with a `Retry-After` header), **503** when overloaded. The 4xx/5xx split tells clients whether *retrying unchanged* can help: 4xx errors normally cannot be fixed by retrying; 5xx and timeouts may be.

## Idempotency keys and safe retries {#sec-idem}

Networks fail in a way that leaves the client ignorant: it sent a request, and the connection dropped before the response. Did the server process it? *The client cannot know.* If the operation is "charge the card" or "send the email", blind retry may do it twice; giving up may do it zero times.

The standard solution is the **idempotency key**. The client generates a unique value (a random UUID) for each *logical* operation and sends it with every attempt. The server records, for each key, the result of the first execution. A retry carrying the same key does not execute again; the server returns the stored result.

{{fig idempotency | A retry with an idempotency key. The first response is lost, the client retries with the same key, and the server returns the stored result instead of charging twice.}}

Implementation sketch for the server:

```python
def handle_create_payment(request):
    key = request.headers["Idempotency-Key"]
    record = store.get(key)                      # shared store, not local memory
    if record and record.fingerprint != hash(request.body):
        return error(422, "key reused with a different request")
    if record and record.status == "done":
        return record.response                   # replay the saved answer
    if record and record.status == "in_progress":
        return error(409, "request in progress")
    store.put_if_absent(key, status="in_progress", fingerprint=hash(request.body))
    response = do_payment(request)               # may itself need a transaction
    store.update(key, status="done", response=response)
    return response
```

Details that matter: store the key with the *request fingerprint* so a reused key with different content is rejected; make `put_if_absent` atomic (otherwise two simultaneous retries both run); keep keys for a bounded time (for example 24 hours); and put the key check and the business effect in the *same transaction* where possible. An idempotency key makes the *client-visible* result stable; it does not make arbitrary side effects (an email already sent) disappear, so the downstream actions must be idempotent too.

## Pagination {#sec-paging}

Returning a million rows in one response is slow and fragile. APIs return results in **pages**.

**Offset pagination:** `GET /pastes?limit=20&offset=40`. Simple and allows jumping to page 3. But the database must walk past the first 40 rows to return the next 20, so deep pages are slow (offset 1,000,000 scans a million rows), and if items are inserted or deleted while the client pages, rows are skipped or repeated.

**Cursor (keyset) pagination:** `GET /pastes?limit=20&after=7Hq2Zx`. The client sends the *last item it saw* (an opaque token encoding the sort key), and the server queries `WHERE (created_at, id) < (cursor values) ORDER BY created_at DESC, id DESC LIMIT 20`. With an index on the sort key this is fast at any depth and stable under inserts. The costs: no random jump to page 50, and the sort key must be unique and indexed.

Table[paging]: Offset versus cursor pagination.

| | Offset | Cursor (keyset) |
|---|---|---|
| Jump to page *n* | Yes | No |
| Deep pages | Slow (cost grows with offset) | Fast (index seek) |
| Stable if data changes | No (skips and duplicates) | Yes |
| Typical use | Small admin lists | Feeds, timelines, large datasets |

## Versioning and compatibility {#sec-version}

Clients cannot all upgrade at once, so evolve APIs **compatibly**. Safe changes: adding a new optional field, a new endpoint, or a new optional parameter. Breaking changes: removing or renaming a field, changing a field's type or meaning, making an optional input required, changing status codes. Follow **Postel's principle** carefully: clients should *ignore unknown fields*, so servers can add them without a new version.

When a break is unavoidable, introduce a new version (`/v2/...` or a header), run both for a deprecation period, measure who still uses the old one, announce a date, then remove. For schema-based RPC such as Protocol Buffers, the rules are explicit: never reuse a field number, never change a field's type, only add optional fields.

## Webhooks and polling {#sec-webhook}

How does a client learn that something finished? **Polling:** repeatedly ask "is it done?" Simple, but wasteful, and latency is bounded by the poll interval. **Webhooks:** the server calls a URL the client registered when the event happens. Efficient and timely, but the server must handle slow or failing receivers (retries with backoff, signatures so receivers can verify the sender, and idempotent event delivery because retries cause duplicates). For high-volume streams, **message queues or streaming APIs** replace both (Chapter {ch:ch-async}).

::: supplement
**Authentication versus authorization at the API.** *Authentication* establishes **who** is calling (verified by a password, an API key, or a signed token such as a JWT or an OAuth 2.0 access token). *Authorization* decides **what that caller may do**. A 401 means "I do not know who you are"; a 403 means "I know who you are and the answer is no". Never trust data supplied by the client for authorization decisions: check ownership and permissions on the server for every request. Chapter {ch:ch-security} treats this in depth.
:::

::: failure
**Failure modes.** Timeouts leaving outcomes unknown (use idempotency keys and, for important work, a status endpoint the client can query); retry storms when many clients retry at once against a struggling server (use exponential backoff with jitter, Chapter {ch:ch-resilience}); breaking changes shipped silently; unbounded page sizes or unfiltered list endpoints that allow one request to read the whole database; inconsistent error formats that make client code brittle.
:::

::: misconception
- *"REST means JSON over HTTP."* REST is a set of constraints (resources, uniform interface, statelessness); many "REST" APIs follow only some of them, which is usually fine.
- *"RPC is old and REST is modern."* They solve different problems; large companies use gRPC heavily internally and REST publicly.
- *"A retry is always safe if the server is correct."* Only if the operation is idempotent or protected by an idempotency key.
- *"HTTP 200 with an error field is friendlier."* It breaks caches, monitoring and generic clients.
:::

::: interview
**Q1. When would you pick gRPC over REST?**
For internal, high-volume service-to-service calls where both ends are under your control: schemas, speed and generated clients win. For public or browser-facing APIs choose REST for ubiquity and cacheability.

**Q2. How do you make a payment endpoint safe to retry?**
Require an idempotency key; store the key with a request fingerprint and result atomically; replay the stored result on retry; reject reuse with a different body; expire keys after a window.

**Q3. Why is cursor pagination better for a feed?**
It is stable when new items arrive and performs the same for any depth because it uses an index seek, while offset pagination slows with depth and skips or duplicates items under change.

**Q4. How do you evolve an API without breaking clients?**
Make only additive changes within a version, tolerate unknown fields, version breaking changes, support the old version through a deprecation period, and watch usage metrics before removal.
:::

::: exercise
1. Design REST endpoints for a library: books, members, and loans (a member borrows a book). Give method, path and success status for creating a loan, listing a member's loans, and returning a book.
2. A client calls `POST /orders` and the connection times out. Describe, step by step, how an idempotency key lets the client recover safely.
3. A feed has 10 million rows. Compare the cost of fetching rows 9,999,980 to 10,000,000 with offset versus cursor pagination.
4. Which of these are breaking changes: adding an optional response field; renaming `userId` to `user_id`; making `email` a required request field; adding a new endpoint?

**Answers.**
1. `POST /members/{id}/loans` body `{bookId}` → 201 with a Location header; `GET /members/{id}/loans?limit=20` → 200; returning: `DELETE /loans/{loanId}` → 204, or `PATCH /loans/{loanId}` setting `returned_at` → 200 (a state change on the same resource).
2. The client generated a key before the first attempt. It retries with the *same* key. If the first attempt succeeded, the server finds the stored result and returns it; if it never arrived, the server executes now. Either way exactly one order exists.
3. Offset must walk past ~10 million rows (cost proportional to the offset); cursor seeks directly in the index and reads 20 rows (cost about the same as page one).
4. Breaking: the rename and the new required field. Not breaking: the optional response field and the new endpoint.
:::

::: summary
- An API is a contract; design it to change compatibly.
- RPC is action-oriented, fast and tightly coupled: ideal internally. REST is resource-oriented, cacheable and universal: ideal publicly.
- Use correct methods and status codes; make errors machine-readable.
- Idempotency keys make retries safe when outcomes are uncertain.
- Cursor pagination scales and is stable; offset is simple but degrades.
- Webhooks push events; polling pulls; both need retry and idempotency handling.
:::

::: revision
- [ ] I can convert an RPC call list into REST resources.
- [ ] I can write the server logic for an idempotency key.
- [ ] I can choose and defend a pagination style.
- [ ] I can list safe and breaking API changes.
:::

::: supplement
**Further reading.** Roy Fielding's dissertation, chapter 5 (the REST constraints); Google's API Improvement Proposals (aip.dev) for resource-oriented design; Stripe's public API documentation on idempotent requests; the Protocol Buffers language guide on updating message types.
:::
