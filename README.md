# System Design: From First Principles to Production

**A free, 305-page system design textbook for students and working engineers.**
Starts from "what happens when you type a URL" and ends at designing real systems, with worked numbers, diagrams, interview questions and exercises with answers in every chapter.

**[Download the PDF](System_Design_Complete_Textbook.pdf)** (2.3 MB)

## Who it is for
- Students and beginners who want one structured path through system design
- Engineers preparing for system design and object-oriented design interviews
- Anyone who wants to understand how large systems are built, scaled and kept running

## What is inside
| Part | Chapters |
|---|---|
| I. Foundations | What system design is; concurrency; data structures; estimation and capacity |
| II. Networking and the entry layer | Networking and request lifecycle; APIs (RPC, REST); CDN, load balancers, proxies |
| III. Data | Relational databases; scaling SQL; NoSQL; consistency, availability, partitioning |
| IV. Performance and asynchrony | Caching; queues, pub/sub, outbox and sagas |
| V. Reliability | Time, coordination and consensus; resilience patterns; microservices |
| VI. Security and operations | Security and privacy; observability, SLOs, disaster recovery; deployment, cost, capacity |
| VII. Interviews and worked systems | Interview method; Pastebin, Twitter timeline, web crawler, Mint, social graph, query cache, sales rank, scaling to millions; payments and notifications |
| VIII. Object-oriented design | Hash map, LRU, call center, cards and blackjack, parking lot, chat, circular buffer, with **tested code** |
| IX. Practice | 23 more design questions with starting sketches; reading real-world architectures |
| Appendices | Revision sheets and formulas, coverage matrix, glossary, references, index |

Every chapter has learning objectives, key terms, worked examples with units and stated assumptions, failure modes, common misconceptions, interview Q&A, exercises with answers, a summary and a revision checklist.

## Repository layout
- `System_Design_Complete_Textbook.pdf`: the book
- `code/`: runnable examples from the OO chapter (`pytest`, 13 tests)
- `source/`: Markdown chapters, figure sources and build scripts to rebuild the PDF
- `docs/`: coverage matrix, references, QA report

## Quality and honesty notes
- Automated checks (page size, fonts, links, bookmarks, contents page numbers, margins) and a visual pass over every page are described in [`docs/QA_REPORT.md`](docs/QA_REPORT.md).
- Capacity numbers in examples are **assumptions for practice**, not benchmarks.
- Content was written from the author's knowledge and not verified online; reference links were not re-fetched. Found a mistake? Please open an issue.

## Credit and licence
The syllabus follows the open-source [System Design Primer](https://github.com/donnemartin/system-design-primer) by Donne Martin (CC BY 4.0). All explanations, diagrams, tables and code here were written for this book.

Licensed under [CC BY 4.0](LICENSE): share and adapt freely with credit.

## Contributing
Corrections and improvements are welcome through issues and pull requests. Rebuild instructions are in `source/README.md`.

If this helped you, a star on the repo helps other students find it.
