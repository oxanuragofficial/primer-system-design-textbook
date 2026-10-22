%part Part VII | Design Interviews and Worked Systems | A repeatable method for open-ended design problems, then eight complete worked designs and two end-to-end exercises.
%derived Notebook chapter 11 (the four steps, the 20-point checklist, the reusable question bank, common mistakes) and the "how to use" study plan
%added the 45-minute timeline, communication techniques, level expectations, a scoring rubric, the standard answer template used by every case study, and a practice routine
# The System Design Interview Method {#ch-interview}

::: objectives
After this chapter you can:

- lead an open-ended design conversation using the four steps within a 45-minute plan;
- apply the 20-point checklist so no important area is skipped;
- communicate trade-offs, numbers and failure modes in a structured way;
- recognise what interviewers look for at different levels, and avoid the common mistakes;
- practise effectively using the answer template used by every case study in this part.
:::

::: prereq
Chapters {ch:ch-intro} to {ch:ch-cloud}. This chapter organises what you already know into a method; it adds almost no new technology.
:::

::: terms
Open-ended problem
: A task with no single correct answer, judged by the quality of reasoning and trade-offs.

Whiteboard (or shared canvas)
: The drawing surface used to sketch the design while talking.

Deep dive
: Going into detail on one or two components where the problem is hardest.

Trade-off narration
: Saying aloud what each choice gains, costs and when you would choose differently.
:::

## What the interview is testing {#sec-test}

A system design interview is **not** a quiz with a hidden answer. It is a simulation of the first hour of a design meeting with a colleague. The interviewer wants evidence of several skills at once:

- **Problem framing**: do you ask questions and pin down requirements before designing?
- **Quantitative judgement**: do you use numbers to choose between designs (Chapter {ch:ch-estimation})?
- **Breadth**: do you know the standard components and when each applies?
- **Depth**: can you go deep on one hard part, such as a data model, a consistency rule, or a failure scenario?
- **Trade-off thinking**: can you say what you give up?
- **Communication**: can the interviewer follow your reasoning? Do you adapt when they redirect you?
- **Pragmatism**: do you start simple and scale only when pressure justifies it?

The problem is deliberately **under-specified**, and the interview is deliberately **interactive**: hints from the interviewer are signals to follow, not traps.

## The four steps and the 45-minute plan {#sec-steps}

{{fig timeline | A 45-minute plan. Spend the first ten minutes on requirements and numbers, then shape the design, then go deep where the problem is hard, and keep time to scale and discuss failure.}}

### Step 1: use cases, constraints and assumptions (about 10 minutes)

Gather requirements and **scope** the problem. Ask who will use it and how, how many users, what the inputs and outputs are, how much data, how many requests per second, the read-to-write ratio, and which qualities matter (latency, availability, consistency, durability). State **assumptions** explicitly and get agreement ("I will assume 100 million pastes per month, ten times more reads than writes; stop me if that is wrong"). Then **estimate** (Chapter {ch:ch-estimation}): requests per second, storage, bandwidth, memory.

### Step 2: high-level design (about 10 minutes)

Sketch the main components and connections: clients, entry layer, services, data stores, caches, queues. **Justify each component** by tying it to a requirement or number ("a cache because reads are 100 times writes"). Define the **API** and the **data model** briefly. **Trace one request** from user to storage and back, and one write path. Resist adding components for their own sake.

### Step 3: design the core components (about 15 minutes)

Go **deep where the problem is hard**. For a URL shortener: key generation and collisions, the schema, the lookup path. For a feed: fan-out strategy and the celebrity problem. For a crawler: the frontier, politeness and duplicate detection. Choose one or two such areas, ideally those the interviewer shows interest in, and think aloud through alternatives. Include data models, indexes, consistency requirements and what happens on failure.

### Step 4: scale the design (about 10 minutes)

Find bottlenecks and fix them with the tools of the previous chapters: load balancing, horizontal scaling, caching, replication, sharding, queues. Discuss **availability and failure** (what if a node, zone or dependency dies?), **security**, **monitoring**, and **alternatives with trade-offs**. Close by re-walking a request and listing two or three improvements for "more time".

## The 20-point checklist {#sec-checklist}

The four steps expand into a fuller list. You do not have to cover every row in depth, but you should *touch* each one, spending time where the problem is hard.

Table[checklist]: The 20-point checklist.

| # | Item | Typical content |
|---|---|---|
| 1 | Clarify the problem | Goal, users, what is in and out of scope |
| 2 | Functional requirements | The key features (verbs) |
| 3 | Non-functional requirements | Latency, availability, consistency, durability, security |
| 4 | Scale | Users, daily active users, growth |
| 5 | Traffic estimate | Reads and writes per second, peak |
| 6 | Storage estimate | Bytes per item, retention, replication |
| 7 | API design | Endpoints, request and response shapes, errors |
| 8 | Data model | Entities, keys, indexes, SQL or NoSQL and why |
| 9 | High-level architecture | Boxes and arrows with justification |
| 10 | Request flow | Read and write paths end to end |
| 11 | Core components | The hard part in depth |
| 12 | Bottlenecks | What saturates first, and why |
| 13 | Scaling | Cache, replicas, shards, queues, CDN |
| 14 | Availability | Redundancy, failover, zones |
| 15 | Consistency | What may be stale, for how long, why acceptable |
| 16 | Failure handling | Timeouts, retries, degradation, recovery |
| 17 | Security and privacy | AuthN, AuthZ, abuse, data protection |
| 18 | Monitoring and operations | Metrics, alerts, deployment, cost |
| 19 | Trade-offs and alternatives | What you gave up, other options |
| 20 | Summary and next steps | Two-minute recap, improvements |

## Communicating well {#sec-comm}

Technique matters as much as content.

- **Think aloud, structure out loud.** "First I will clarify requirements, then estimate, then sketch. I will go deep on key generation." Signposting keeps the interviewer oriented.
- **Draw as you talk**, keep the diagram clean, label arrows with *what flows* (HTTP, event, SQL), and number the steps of a flow.
- **Anchor on numbers.** Replace "a lot of traffic" with "about 4,000 reads per second, peak 10,000".
- **Narrate every trade-off** in a repeatable form: *"We could use A, which gains X but costs Y. Given that our requirement is Z, I choose A, and I would revisit if W."*
- **Start simple, then evolve.** "The simplest design is one server and one database. At our numbers the first thing to break is the database reads, so I add a cache."
- **Check in** at transitions ("is this the area you want me to go deeper on?") and **follow hints**.
- **Admit gaps** honestly ("I have not used that database; I would expect X; I would verify Y"). Fabricating certainty is worse than a measured "I don't know, here is how I would find out".
- **Own the time**: if a topic is running long, say so and move on.

::: worked
**Narrating a trade-off well.** *Question:* "How will you generate the short codes?"
*Weak answer:* "I'll use a hash." 
*Strong answer:* "Two options. One: hash the long URL with MD5 and take the first seven Base62 characters. It is stateless and the same URL gives the same code, but different URLs can collide, so I must check and retry, and 7 characters only gives 62⁷ ≈ 3.5 trillion codes. Two: allocate numeric ids from a counter and encode them in Base62: no collisions, but a central counter is a bottleneck and ids are guessable, which may matter for private pastes. At roughly 40 writes per second either works; I would pick the pre-allocated id ranges per server, with a random component if guessability matters, and I would add a unique constraint as a safety net." It names options, numbers, costs and a decision.
:::

## What interviewers expect at different levels {#sec-expectlevels}

Expectations rise with seniority; calibrate your emphasis.

Table[levelexp]: Typical expectations by level (indicative, not a rule).

| Level | Expected | Differentiators |
|---|---|---|
| Early career | A working design for moderate scale; correct use of core components (load balancer, cache, SQL); clear communication | Asking good questions; understanding why components exist |
| Mid-level | Sound estimates; sensible data models; scaling plan; some failure handling | Making and defending trade-offs; going deep on one component |
| Senior | Leads the discussion; chooses depth wisely; consistency, availability and operations; cost and migration awareness | Anticipating bottlenecks and failure modes; evolution over time |
| Staff and above | Frames the problem and success criteria; cross-system impact; organisational and long-term considerations | Simplifying; risk management; saying no to unnecessary complexity |

## Mistakes to avoid {#sec-mistakes}

::: warning
**Common mistakes.** Jumping straight into a database schema or a favourite technology before requirements. Drawing a perfect "final" architecture from memory without reasoning (reciting a company's diagram instead of deriving from the load). Ignoring numbers. Never naming a failure mode. Over-engineering (microservices and five databases for a hundred requests per second). Going silent while thinking. Defending a choice instead of re-examining it when the interviewer hints at a problem. Spending thirty minutes on one component and never scaling. Talking only about the happy path.
:::

## A reusable answer template {#sec-template}

Every case study in this part follows the same skeleton so you can internalise it: **problem and requirements; scale estimate; API; data model; high-level design; core flows; deep dive on the hard part; scaling and bottlenecks; failure handling, security and operations; trade-offs and alternatives; lessons and follow-ups.** In practice, memorise the *questions* rather than a script.

Table[qbank]: A reusable question bank to ask yourself at every box.

| Question | What it exposes |
|---|---|
| Why does this component exist? What breaks without it? | Unjustified boxes |
| What happens at ten times the traffic? Which resource saturates first? | Bottlenecks |
| What happens if this server, database, zone fails? How do we detect and recover? | Availability gaps |
| What may be stale here, and for how long? | Consistency decisions |
| What are we giving up with this choice? | Trade-offs |
| What would I do differently with twice the budget, or half? | Cost awareness |
| How would a malicious user abuse this? | Security gaps |
| How will we know it is broken? | Observability |

## Practising effectively {#sec-practice}

Reading designs is not the same as producing them. A productive routine:

1. **Pick a problem** (Chapters {ch:ch-pastebin} to {ch:ch-aws} and the practice bank in {ch:ch-practice}).
2. **Attempt before reading**: cover the solution, set a 45-minute timer, and sketch your own design on paper, talking aloud or recording yourself.
3. **Compare** with the worked solution: what did you miss in requirements, numbers, data model, failures?
4. **Redo the weakest part** in 10 minutes.
5. **Practise with a person** if possible (a mock interview), asking them to interrupt and challenge assumptions.
6. **Keep a trade-off notebook**: for each technology, one line each for "gains", "costs", "use when".

::: supplement
**A simple scoring rubric for mock interviews.** Score each dimension 1 (weak) to 4 (strong): *requirements and scoping*; *estimation*; *architecture and component choice*; *data model and APIs*; *depth on the hard part*; *scaling and bottlenecks*; *reliability and failure handling*; *trade-off articulation*; *communication and time management*. Total out of 36. Practise until no dimension is below 3. Note that *consistency of method* matters more than perfection on any one problem.
:::

::: failure
**Failure modes of the interviewee.** Running out of time with the design half-finished; being unable to recover after a wrong assumption; getting stuck on a detail the interviewer does not care about; contradicting earlier statements (a strongly consistent store claimed, then a cache without invalidation drawn); forgetting to ask about scale and designing the wrong system; treating the interview as a performance rather than a conversation.
:::

::: misconception
- *"There is one right answer."* Different designs can be right for different assumptions; the reasoning is what is graded.
- *"More components impress."* Justified simplicity impresses; unjustified complexity does not.
- *"Memorising famous architectures is enough."* Interviewers vary the problem; derivation from numbers generalises.
- *"Interviewers want me to know their tools."* They want the underlying concepts; name a technology as an example, but argue from properties.
:::

::: interview
**Q1. How do you start a design interview?**
By clarifying requirements and scope, stating assumptions and estimating scale, before drawing anything.

**Q2. How do you decide where to go deep?**
Pick the component that is hardest or most distinctive for the problem and where the interviewer shows interest (for a feed, fan-out; for a crawler, the frontier; for a shortener, key generation).

**Q3. How do you handle an interviewer's challenge to your design?**
Treat it as information: restate the concern, evaluate it with numbers or failure scenarios, and either adjust the design or explain the trade-off and the conditions under which you would change it.

**Q4. What do you do if you do not know a technology?**
Say so, describe the properties you would need, reason from principles, and indicate how you would verify.
:::

::: exercise
1. Write the questions you would ask in the first five minutes for "design a ride-hailing service".
2. Spend ten minutes producing the 20-point checklist's items 1 to 6 for "design a photo-sharing service": requirements, scale and estimates.
3. Rehearse narrating one trade-off aloud in the form "We could ... which gains ... but costs ...; given ..., I choose ...".
4. Review a previous design you made: which of the 20 points did you skip?

**Answers (model for 1).** Who are the users (riders, drivers, both)? Which features are in scope (request ride, matching, pricing, payments, ratings, scheduled rides)? Which regions and how many daily rides? What is the latency target for matching? How accurate and how frequent are location updates (every few seconds)? What are availability and consistency needs (a driver must not be double-booked)? Out-of-scope items (pooling, food delivery)? Then estimate: rides per second, location updates per second (usually dominant), storage of trip history.
:::

::: summary
- The interview tests framing, numbers, breadth, depth, trade-offs and communication, in an open-ended conversation you lead.
- Four steps: requirements and estimates; high-level design; core components; scale and failure; budget roughly 10, 10, 15 and 10 minutes.
- The 20-point checklist ensures coverage; the question bank exposes gaps.
- Narrate trade-offs in a standard form, anchor on numbers, start simple, signpost, check in.
- Practise by attempting first, comparing, redoing, and rehearsing aloud.
:::

::: revision
- [ ] I can recite the four steps and the 45-minute plan.
- [ ] I can list the 20 checklist items.
- [ ] I can narrate a trade-off in the standard form.
- [ ] I can name five common mistakes.
:::
