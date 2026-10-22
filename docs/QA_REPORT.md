# QA report: System_Design_Complete_Textbook.pdf

## Result
- 305 pages, A4 (all pages 595 x 842 pt), 32 chapters in 9 parts, 4 appendices (A revision sheets and formulas, B coverage matrix, C glossary, D references), plus an auto-generated index (97 terms).
- 86 figures drawn from source (Graphviz, SVG and a custom sequence-diagram renderer). Roughly 94,000 words.
- 13 unit tests for the object-oriented chapter's code, run and passing.

## Automated checks actually run
| Check | Result |
|---|---|
| PDF opens and parses (pypdf, poppler) | Pass |
| All pages A4 | Pass (305 of 305) |
| Text extractable on every page | Pass; no replacement characters |
| Fonts embedded | Pass (12 fonts, 0 unembedded) |
| Metadata (title, author, subject, keywords) | Present |
| Bookmarks | 341, hierarchical (parts, chapters, sections) |
| Internal links | 2,026 present, 0 broken named destinations. External links: none (URLs are plain text) |
| Duplicate anchor ids | 1 found (`sec-levels`), fixed; now 0 |
| Cross-references (figures, tables, sections, chapters) | Strict build reports 0 unresolved |
| Contents page numbers vs real heading pages | 221 of 221 match |
| Empty pages | None |
| Near-empty pages | 10, all of them part-divider pages (intended) |
| Words outside the page's safe margins | 0 |
| Unresolved markup (`{fig:...}`, `:::`, etc.) | None |
| Notebook sections vs coverage matrix | 62 notebook headings checked by title; 54 matched directly, 8 are covered under differently worded rows (OO design method and designs, Mint, real-world architectures, symptom table) or superseded (the notebook's own coverage map) |

## Visual inspection
All 305 pages were viewed as contact sheets (12 pages per image, 45 dpi). That is enough to catch layout defects: overlaps, clipping, blank pages, broken figures, orphaned boxes. It is not enough to proofread small print.
Defects found and fixed during inspection:
- Contents numbers all showing "1" (page-counter reset broke the lookup); numbering now continuous.
- Empty index (no markers existed); index is now generated automatically.
- Four chapters ending with a nearly empty page holding only a "Further reading" box; those lists were moved into Appendix D.
- Three figures with labels scaled below about 7.5 pt; redrawn tall and narrow.
- Stale running header on the index page.
- Box titles stranded at the bottom of a page (rule added after the last full rebuild; the final build includes it, but those pages were not re-viewed).

## Known limitations and unresolved items
- Some pages end with white space because figures are kept whole rather than split.
- Page numbering is continuous across the book. Front matter is in roman numerals and Chapter 1 starts on page 9.
- Index entries come from the glossary terms plus a short extra list and link to the first use per chapter; it is not an exhaustive hand-built index.
- Content accuracy was written from knowledge. No web verification was done in this session. The reference list and the notebook's company and blog links were not re-fetched (the book says so in-text).
- All capacity numbers in worked examples are labelled assumptions. The arithmetic in the revision tables and the exercise answers was spot-checked by hand, not exhaustively.
- Code was tested single-threaded only. The 13 tests do not cover concurrency.
- Source content that was unreadable: none.

## Supplemental material
Content not in the notebook is labelled "supplemental" or "added in this book" in each chapter opener; Appendix B lists it.
