%part Part I | Foundations | The vocabulary, the machine-level background and the arithmetic that every later chapter relies on.
%derived Notebook chapter 1 (Foundations: the life of a request, performance vs scalability, latency vs throughput, scaling up vs out) and the "How to use this notebook" page
%added requirements framework, percentiles, bottleneck thinking, the design loop
# What System Design Is {#ch-intro}

::: objectives
After this chapter you can:

- define *system design* and describe the path a request takes through a typical web system;
- separate functional requirements, non-functional requirements and constraints;
- tell a **performance** problem from a **scalability** problem and say why the difference changes the fix;
- explain latency, throughput and percentiles, and why averages hide the experience of unlucky users;
- compare vertical and horizontal scaling and explain why *stateless* servers make horizontal scaling easy;
- state the design loop used throughout this book: requirements, numbers, boxes, bottlenecks, trade-offs.
:::

::: prereq
None. You should be comfortable with the idea of a program that talks to another program over a network, and you should have used a website or a mobile app. Everything else is introduced here.
:::

::: terms
Server
: A computer (or a program on one) that waits for requests and answers them.

Client
: The program that sends requests: a browser, a mobile app, or another server.

Request / response
: One message asking for work, and the message returned with the result.

Latency
: The time one operation takes from start to finish, for example 120 milliseconds (ms) for a page request.

Throughput
: How many operations the system completes per unit of time, for example 5,000 requests per second (RPS).

Scalability
: The ability to handle more load by adding resources, with performance improving roughly in proportion.

Bottleneck
: The single resource that limits the whole system right now (CPU, memory, disk, network, a lock, a database).

Stateless / stateful
: A stateless server keeps nothing between requests that another server could not recreate; a stateful one remembers things locally.

Trade-off
: A choice where improving one property (say, speed) costs another (say, freshness of data or money).
:::

## What system design is {#sec-what}

**System design** is the activity of deciding which components a software system needs, what each one is responsible for, how they communicate, where data lives, and what happens when parts fail or when traffic grows. It is not about writing the code inside one function. It is about the shape of the whole.

Why does this need to be done *on purpose*? A program that serves ten users from one laptop needs almost no design: one process, one file or database, done. As usage grows, four pressures appear, and each forces a design decision:

1. **Load.** One machine can only do so much work per second. Beyond that you need several machines, and something must decide which machine handles which request.
2. **Data.** Data can outgrow one disk, and many users reading and writing at once can overwhelm one database. You must decide how to copy, split and cache data.
3. **Failure.** Disks die, networks drop packets, software has bugs, and deployments go wrong. With many machines, *something* is always failing. The design must keep working anyway.
4. **Change.** Teams grow and features multiply. The structure of the system determines whether ten engineers can work independently or trip over each other.

A useful way to see all of this at once is to follow a request.

### The path of a request

Suppose a user opens a photo-sharing site and loads their timeline. Roughly, the following happens (every step is taught in a later chapter):

1. The browser asks the **Domain Name System** (DNS) to turn `photos.example` into an Internet Protocol (IP) address ({sec:dns}).
2. Static files such as images, scripts and style sheets may be answered by a **content delivery network** (CDN) located near the user ({sec:cdn}).
3. Dynamic requests reach a **load balancer**, which picks one of many application servers ({sec:lb}).
4. A **web server or reverse proxy** terminates the secure connection and forwards the request ({sec:proxy}).
5. An **application server** runs the business logic. It first asks a **cache** for ready-made answers ({ch:ch-cache}), and on a miss reads a **database** ({ch:ch-sql}).
6. Slow or non-urgent work (resizing a new photo, sending a notification) is placed on a **queue** and done later by **workers** ({ch:ch-async}).
7. Large files such as the photos themselves live in an **object store**.

{{fig request-path | The life of a request. Solid arrows are the synchronous path the user waits for; dashed arrows are background work after the response. The numbers follow the steps above, with the load balancer and reverse proxy (steps 3 and 4) drawn as one box. Every later chapter zooms into one box.}}

Read {fig:request-path} left to right. The **solid arrows** show what the user waits for: name lookup, then (for static content) the CDN, otherwise the load balancer and proxy, the application server, and finally cache or database. The **dashed arrows** show work the application server hands to a queue so the user does not wait: a worker picks the job up later and may write results to the object store or database. The cache sits *beside* the database because the application checks it first.

::: analogy
**A restaurant.** DNS is the phone book that gives you the address. The CDN is a take-away counter that hands out popular dishes without troubling the kitchen. The load balancer is the host who seats you at a free table. The application server is the waiter, the cache is the pass where finished dishes wait, and the database is the pantry. A queue is the order rail: the waiter clips a ticket for a slow dish and moves on, instead of standing in the kitchen.
:::

Note the pattern: nearly every box exists to do one of three jobs — make the path **faster** (CDN, cache), make it **bigger** (load balancer, more servers, sharding) or make it **safer** (replication, queues, retries). When you meet a new component later, ask which of the three it serves and what it costs.

## Requirements, constraints and scope {#sec-req}

No design is good or bad in the abstract; it is good or bad *for a set of requirements*. A system serving a classroom of thirty can use one database server happily, while a payments network cannot. Therefore every design starts by writing down what must be true.

**Functional requirements** describe *what the system does*: "a user can post a message", "a user can follow another user", "the system shortens a URL and redirects". They are features, usually phrased as verbs.

**Non-functional requirements** (also called *quality attributes*) describe *how well* it does them. The ones that most often drive architecture are:

Table[nfr]: Common non-functional requirements and the questions that sharpen them.

| Quality | What it means | Sharpening question |
|---|---|---|
| Performance | Time per operation | What is acceptable for the 95th or 99th percentile? |
| Scalability | Handling growth | How many users, requests per second, and how fast will they grow? |
| Availability | Fraction of time the service works | Is 99.9% enough, or is every minute of downtime costly? |
| Durability | Data is not lost once acknowledged | What if the last second of writes disappears? |
| Consistency | Everyone sees the same data | Can a reader see slightly stale data? For how long? |
| Security & privacy | Only the right people do the right things | Who are the attackers? What data is regulated? |
| Cost | Money and operational effort | What is the budget, and who runs it at 3 a.m.? |

**Constraints** are fixed facts that limit the solution: "must run on the company's existing cloud", "must store data in one country", "team of three engineers", "launch in six weeks". Constraints are not goals; they are walls.

**Scope** is the explicit list of what is *not* being designed. Stating scope out loud ("search ranking is out of scope; we only need keyword matching") prevents an open-ended problem from consuming all your time, in an interview or in real work.

::: worked
**Turning a vague idea into requirements.** The request: *"Build a service like a text-sharing site where you paste text and get a link."*

- *Functional:* create a paste and receive a short URL; open the URL to view the text; optionally let pastes expire.
- *Non-functional:* reads far outnumber writes (assume 10 reads per write); a viewer should see a paste within about 200 ms at the 95th percentile; stored pastes must not be lost (durability); 99.9% availability.
- *Constraints:* a team of two; use managed cloud services.
- *Scope:* user accounts, editing and syntax highlighting are out of scope.

Notice how the non-functional line "reads outnumber writes 10 to 1" already suggests caching, and "must not be lost" already rules out keeping pastes only in memory. Requirements *are* the first design decisions. This exact problem is worked through in full in {ch:ch-pastebin}.
:::

## Performance versus scalability {#sec-perfscale}

These two words are used loosely but mean different things, and mixing them up leads to expensive mistakes.

- A **performance problem** means the system is slow *even for a single user*. A badly written query that scans a ten-million-row table takes seconds no matter how quiet the system is.
- A **scalability problem** means the system is fast for one user but slows down (or fails) as load grows. A well-written query is fast; but if every request queues on one shared lock, ten users each wait for nine others.

The diagnostic test is simple: *measure one request on an otherwise idle system.* If it is already slow, you have a performance problem; profile and fix the code, query, or algorithm. If it is fast when alone and slow under load, you have a scalability problem; look for a shared resource that serialises work.

A system is **scalable** when adding resources improves capacity in rough proportion: doubling the servers lets you serve close to double the traffic. Load can grow in two ways: *more units of work* (more users, more requests) or *larger units of work* (a dataset that keeps growing, so each query touches more data). Different techniques address each; sharding, for example, helps when data grows, while load balancing helps when requests multiply.

::: warning
**Buying servers for a performance problem.** If one request takes ten seconds because of a missing database index, ten servers give you ten slow requests at the same time, not a fast one. Always find out which kind of problem you have *before* spending money.
:::

## Latency, throughput and percentiles {#sec-latency}

**Latency** is how long one operation takes. **Throughput** is how many operations complete per unit of time. They are related but not the same, and improving one does not automatically improve the other.

::: analogy
A highway. Latency is the time *one car* needs to travel from A to B. Throughput is the number of cars per hour that pass a point. Adding lanes raises throughput without making any single car arrive sooner. Raising the speed limit lowers latency but, if cars are spaced farther apart for safety, may not raise throughput much.
:::

Near capacity, the two interact badly. Requests arrive, wait in a queue for a free worker, and *then* run. As utilisation approaches 100%, queue waiting time explodes, so latency climbs steeply while throughput flattens at its maximum (see {fig:latency-curve}). This is why running a system at 95% utilisation is dangerous: a small bump in traffic turns into very long waits. Many teams plan to stay well below saturation (often 50% to 70% at peak) to leave room for bursts.

{{fig latency-curve | Latency stays flat while the system has spare capacity, then rises steeply near saturation. Throughput stops growing at the capacity limit; extra offered load only lengthens queues.}}

### Why averages mislead

If 99 requests take 100 ms and one takes 10 seconds, the **average** is about 199 ms: a number that describes *nobody's* experience. Engineers therefore report **percentiles**. The *p50* (median) is the value half of requests beat. The *p95* is the value 95% of requests beat; the *p99* beats 99%. The slowest few per cent are called the **tail**.

Tail latency matters more than it first appears. A single page view may trigger dozens of internal calls. If each call has a 1% chance of being slow, a page that makes 100 calls will hit at least one slow call about 63% of the time (1 − 0.99¹⁰⁰ ≈ 0.63). The user experiences the *worst* of the many calls, so internal p99 becomes external median. We return to this in {ch:ch-resilience}.

Table[lat]: A tiny dataset showing why the mean is not enough (ten requests, in milliseconds).

| Request | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Latency (ms) | 90 | 95 | 98 | 100 | 102 | 105 | 110 | 115 | 120 | 2,400 |

The mean is 333.5 ms, yet nine of ten users saw 120 ms or better. The median is 103.5 ms and the maximum is 2,400 ms; reporting only the mean would misrepresent both the typical and the unlucky user.

## Scaling up and scaling out {#sec-scale}

Once one server is not enough, there are two directions.

**Vertical scaling (scale up)** means buying a bigger machine: more CPU cores, more memory, faster disks. It is simple because the software does not change. Its limits are that machines have a maximum size, the price rises faster than the capacity at the top end, and a single machine remains a **single point of failure** (SPOF): if it dies, everything stops.

**Horizontal scaling (scale out)** means adding more ordinary machines and spreading the work among them. It has no hard ceiling and tolerates the loss of individual machines, but it demands software that can run in many copies, and it introduces coordination problems: where does shared data live, how are requests spread, and what happens when two machines disagree?

{{fig scale-up-out | Vertical scaling replaces one machine with a larger one; horizontal scaling adds machines behind a load balancer. The second approach can grow further and survive failures, at the price of coordination.}}

Table[scaleupout]: Vertical versus horizontal scaling.

| | Vertical (scale up) | Horizontal (scale out) |
|---|---|---|
| Change required | Usually none | Software must run as many copies |
| Cost curve | Rises steeply at the high end | Roughly linear with commodity machines |
| Failure | One machine = one SPOF | Loss of one machine is tolerated |
| Upper limit | Largest machine available | Limited by coordination, not hardware |
| Typical first use | Databases, early startups | Web and application tiers |

### Why stateless servers scale out easily

The easiest thing to scale out is a **stateless** server. If a server keeps no per-user data in its own memory or disk, then *any* server can handle *any* request, and a load balancer can send each request anywhere. If a server keeps the user's login session in local memory, the user must always return to *that* server (a design called *sticky sessions*), and losing the server logs the user out.

The fix is to move state out of the server into a shared place: a database, a distributed cache, or a signed token held by the client. After that, servers become interchangeable and can be added or removed at will. We use this idea repeatedly: *keep the application tier stateless and push state into specialised stores that are designed to hold it.*

::: supplement
**Amdahl's law: why scaling out has limits.** If a fraction *s* of the work is inherently serial (it cannot be split among machines), then no number of machines gives a speed-up greater than 1/*s*. If 5% of each request goes through one lock or one database row, the maximum speed-up is 1/0.05 = 20×, however many servers you add. Practical lesson: when scaling stops working, look for the serial section, which is usually shared state. The *Universal Scalability Law* adds a second effect, coordination cost, which can make throughput *fall* when too many nodes talk to each other.
:::

## Trade-offs: the central skill {#sec-tradeoff}

Almost every technique in this book buys something by spending something else. Learning to name both sides is the single most valuable habit in system design, and interviewers listen for it more than for any specific technology.

Table[tradeoffs]: Familiar techniques and what each one costs.

| Technique | You gain | You pay |
|---|---|---|
| Cache | Lower latency, less database load | Stale data, invalidation complexity, extra component |
| Replication | Availability, read capacity | Replication lag; complexity of failover |
| Sharding | Write capacity, data size | Cross-shard queries, rebalancing, operational load |
| Queue | Absorbs bursts, decouples services | Delay, duplicate or reordered messages, harder debugging |
| Microservices | Independent teams and deployment | Network calls, distributed failure, data consistency problems |
| Denormalisation | Fast reads | Duplicated data, harder writes |
| Strong consistency | Simple reasoning | Higher latency, lower availability under partitions |

::: note
**Clarification on "this improves scalability".** The original notes sometimes say a technique "improves scalability". That is shorthand. More precisely, a technique improves scalability *under a stated condition*: a cache improves read scalability **if the same data is read many times between changes** (a high hit ratio); it does nothing for write scalability and can worsen consistency. Whenever you write "X improves Y", add "when Z" and "at the cost of W".
:::

## The design loop {#sec-loop}

The remainder of this book repeats one loop. Learn it now and apply it to every problem, from the worked case studies to the exercises.

1. **Clarify requirements.** Functional, non-functional, constraints, scope.
2. **Estimate.** Turn "millions of users" into requests per second, bytes stored and bandwidth ({ch:ch-estimation}).
3. **Sketch the simplest design that could work.** Often one server and one database.
4. **Find the bottleneck.** Measure or reason about which resource saturates first.
5. **Relieve the bottleneck with the cheapest suitable technique**, naming its cost.
6. **Repeat from step 4** until the requirements are met, then examine failure modes and security.
7. **Record the decisions and trade-offs** so others can understand and revise them.

The discipline of step 3 is often skipped. Start simple and let measured or estimated pressure justify each added component; every box you add must be built, monitored, secured, paid for and debugged.

::: failure
**Typical failure patterns at the foundation level.** (1) The single server is a SPOF and dies. (2) A hidden shared resource (one database, one lock, one log file) serialises everything. (3) A slow dependency makes every request slow because requests wait on it. (4) A traffic burst arrives faster than capacity can be added. Later chapters give a specific remedy for each: replication ({ch:ch-scaling-sql}), partitioning ({ch:ch-distdata}), timeouts and load shedding ({ch:ch-resilience}), and queues with back-pressure ({ch:ch-async}).
:::

::: misconception
- *"Scalable means fast."* No. A scalable system keeps performance acceptable as load grows; a fast single-user system may collapse under load.
- *"Horizontal scaling is always better."* It is necessary beyond a point, but vertical scaling is simpler and often correct for a database or an early-stage product.
- *"More servers always means more availability."* Only if the servers are independent and nothing shared (database, network, configuration) is a SPOF.
- *"Good design means using many technologies."* Good design means the fewest components that meet the requirements.
:::

::: interview
**Q1. What is the difference between a performance problem and a scalability problem?**
A performance problem is slow for one user; a scalability problem is fast alone but degrades under load. Test with a single request on an idle system. The fix differs: optimise code or queries for the first, remove shared bottlenecks and add capacity for the second.

**Q2. Why do engineers quote p99 latency rather than the average?**
Averages hide the tail. A few very slow requests barely move the mean but make real users unhappy, and in systems where one user action fans out into many internal calls, tail latency dominates the user's experience.

**Q3. Why are stateless servers easier to scale out?**
Because any server can handle any request, a load balancer can distribute freely and servers can be added, removed or replaced without losing user data. State is moved to shared stores built for it.

**Q4. When would you prefer scaling up?**
When the component is hard to distribute (a single relational database early on), when the load is modest, or when simplicity and development time matter more than headroom. Know the ceiling and have a plan for when you reach it.
:::

::: exercise
1. A page loads in 4 s for one user on an idle test machine. A colleague proposes adding five servers. Is this a good first step? Why or why not?
2. Ten request latencies are 80, 85, 90, 90, 95, 100, 100, 105, 110, 900 ms. Compute the mean and the median. Which better describes the typical user?
3. A page needs 50 internal calls, each of which exceeds 200 ms with probability 2%. What is the probability that at least one is slow?
4. Write functional requirements, non-functional requirements, constraints and scope for "a service that sends one-time passwords by SMS".
5. List three places a web application might hold per-user state, and for each say whether it prevents scaling out.

**Answers.**
1. No. It is a performance problem (slow even alone). Profile and fix the slow step first; extra servers would give five slow requests.
2. Mean = 1,755 / 10 = 175.5 ms (sum 80+85+90+90+95+100+100+105+110+900 = 1,755). Median = (95+100)/2 = 97.5 ms. The median describes the typical user; the mean is dragged up by one outlier.
3. 1 − 0.98⁵⁰ = 1 − 0.364 = about 0.636, i.e. roughly 64%.
4. Sample: *functional* send an OTP to a phone number, verify a code, expire codes; *non-functional* delivery within a few seconds at p95, 99.95% availability, rate-limit abuse; *constraints* use an SMS provider's API, comply with local telecom rules; *scope* excludes marketing messages and user accounts.
5. In server memory (blocks scaling out unless sessions are sticky), in a shared cache or database (does not block), in a signed token held by the client (does not block, but the token cannot be revoked easily).
:::

::: summary
- System design is deciding components, responsibilities, communication, data placement and failure behaviour for stated requirements.
- A request path (DNS, CDN, load balancer, proxy, application, cache, database, queue, object store) is the map of the whole book.
- Requirements come first: functional, non-functional, constraints and scope.
- Performance is slowness for one user; scalability is how performance holds as load grows. Diagnose before fixing.
- Latency is time per operation, throughput is operations per time; use percentiles, not averages.
- Scale up is simple but bounded and a SPOF; scale out is unbounded but needs stateless servers and coordination.
- Every technique has a price. Start simple, find the bottleneck, relieve it, name the cost.
:::

::: revision
- [ ] I can draw the request path from memory and say what each box is for.
- [ ] I can list functional and non-functional requirements for a new feature.
- [ ] I can explain p50, p95, p99 and the tail.
- [ ] I can say why stateless servers scale out and where the state goes instead.
- [ ] For any technique I can state what it gains and what it costs.
:::

::: supplement
**Further reading.** Martin Kleppmann, *Designing Data-Intensive Applications* (O'Reilly), chapters 1 and 2 for reliability, scalability and maintainability. Jeff Dean and Luiz André Barroso, "The Tail at Scale", *Communications of the ACM*, 2013, for why tail latency dominates fan-out systems. Neil Gunther's writing on the Universal Scalability Law for the mathematics of coordination cost.
:::
