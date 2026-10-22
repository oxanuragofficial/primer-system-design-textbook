%label D
%added the reference list, compiled for this book
# References and Further Reading {#app-references}

**Provenance and licence.** The curriculum follows the open-source *System Design Primer* by Donne Martin (https://github.com/donnemartin/system-design-primer, licensed under CC BY 4.0). All explanations, diagrams, tables and code in this book were written for it. The links below were not fetched while writing; they are standard, stable references that the reader should check for current editions.

## Books

- Kleppmann, M. *Designing Data-Intensive Applications*. O'Reilly, 2017. The best single book behind Parts III to V.
- Beyer, B., Jones, C., Petoff, J., Murphy, N. R. (eds). *Site Reliability Engineering*. O'Reilly, 2016 (free online). Monitoring, SLOs, incident response.
- Nygard, M. *Release It!* 2nd ed. Pragmatic Bookshelf, 2018. Resilience patterns.
- Xu, A. *System Design Interview* (volumes 1 and 2). Worked interview problems.
- Manning, C., Raghavan, P., Schütze, H. *Introduction to Information Retrieval*. Cambridge University Press, 2008 (free online). Crawling and indexing.
- Tanenbaum, A., van Steen, M. *Distributed Systems*. Background on clocks, consensus and replication.
- Shostack, A. *Threat Modeling: Designing for Security*. Wiley, 2014.
- Anderson, R. *Security Engineering*, 3rd ed. Wiley, 2020 (free online).
- Newman, S. *Building Microservices*, 2nd ed. O'Reilly, 2021.
- Evans, E. *Domain-Driven Design*. Addison-Wesley, 2003.
- Silberschatz, A., Korth, H., Sudarshan, S. *Database System Concepts*. Transactions and storage.

## Papers

- Dean, J., Ghemawat, S. "MapReduce: Simplified Data Processing on Large Clusters." OSDI 2004.
- Ghemawat, S., Gobioff, H., Leung, S.-T. "The Google File System." SOSP 2003.
- Chang, F. et al. "Bigtable: A Distributed Storage System for Structured Data." OSDI 2006.
- DeCandia, G. et al. "Dynamo: Amazon's Highly Available Key-value Store." SOSP 2007.
- Lakshman, A., Malik, P. "Cassandra: A Decentralized Structured Storage System." 2009.
- Corbett, J. et al. "Spanner: Google's Globally-Distributed Database." OSDI 2012.
- Burrows, M. "The Chubby Lock Service for Loosely-Coupled Distributed Systems." OSDI 2006.
- Ongaro, D., Ousterhout, J. "In Search of an Understandable Consensus Algorithm" (Raft). USENIX ATC 2014.
- Lamport, L. "Time, Clocks, and the Ordering of Events in a Distributed System." CACM 1978.
- Brewer, E. "CAP Twelve Years Later: How the 'Rules' Have Changed." IEEE Computer 2012; Gilbert, S., Lynch, N. "Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services." 2002.
- Abadi, D. "Consistency Tradeoffs in Modern Distributed Database System Design" (PACELC). IEEE Computer 2012.
- Sigelman, B. et al. "Dapper, a Large-Scale Distributed Systems Tracing Infrastructure." Google Technical Report 2010.
- Kreps, J. "The Log: What every software engineer should know about real-time data's unifying abstraction." 2013.
- Heydon, A., Najork, M. "Mercator: A Scalable, Extensible Web Crawler." 1999.
- Manku, G., Jain, A., Das Sarma, A. "Detecting Near-Duplicates for Web Crawling." WWW 2007.
- Karger, D. et al. "Consistent Hashing and Random Trees." STOC 1997.
- Bloom, B. "Space/Time Trade-offs in Hash Coding with Allowable Errors." CACM 1970.
- Garcia-Molina, H., Salem, K. "Sagas." SIGMOD 1987.

## Standards and specifications

- RFC 9110 (HTTP semantics), RFC 9113 (HTTP/2), RFC 9114 (HTTP/3), RFC 9000 (QUIC), RFC 8446 (TLS 1.3), RFC 1035 (DNS).
- RFC 6749 (OAuth 2.0), RFC 7636 (PKCE), RFC 7519 (JSON Web Token).
- NIST SP 800-63B, Digital Identity Guidelines: Authentication and Lifecycle Management.
- OWASP Top 10 and OWASP Cheat Sheet Series for web security.
- OpenTelemetry specification for traces, metrics and logs.

## Other resources

- The *System Design Primer* repository and its linked articles.
- Company engineering blogs listed in Section {sec:sec-rw-blogs}.
- The Common Crawl project (public web crawl data).

::: note
**Verification status.** References were written from the author's knowledge of these works; titles, venues and years should be confirmed before citing them formally. The book makes no claim that any link was reachable at the time of writing.
:::
