# Write-up

## Architecture

Route by file type, extract with the cheapest tool that can do the job, then put
every record through one shared normalisation and confidence step.

```
documents/ -> router -> extractor -> normalise -> sink (CSV + SQLite)
                          |
                          +-- .json  deterministic adapters, no model
                          +-- .pdf   pdfplumber text -> model
                          +-- .eml   MIME parse, text/plain -> model
                          +-- .png/.jpg  base64 -> vision model
```

The main decision is that **the clean JSON exports never touch a model**. They
are already structured. The only problem is that no two suppliers agree on field
names, and that is a mapping problem: deterministic, free, instant, testable.
Sending them to a model would add latency and cost in exchange for a chance of
being wrong about data that was never ambiguous.

The cost is that a new supplier export needs a new adapter, and `detect()` will
raise rather than guess. At three exports that is clearly right. At thirty I
would keep the adapters for the suppliers that matter and add a model-backed
fallback for the long tail, with the adapter output treated as ground truth in
tests. What I would not do is replace the adapters with a model because the
adapters felt like boilerplate.

The second decision is that **arithmetic stays in Python**. The model is asked
for what the document says, never for a division. If a document gives a pack
price and a pack size, the model returns both and leaves `price_per_unit` null;
`normalise.py` does the division and records how. Arithmetic done by a model is
arithmetic somebody has to check.

## The messy cases

**Email.** The figures are in prose, and the substantive problem in this thread
is that the P.S. corrects line 1 from 0.128 to 0.134 per tablet. Two things
handle it. The prompt states that a later figure supersedes an earlier one and
that the superseded value goes in `notes`, which is what happened: the record
carries 0.134 with the correction described. Then, independently, the extractor
scans the body for correction language and, if it finds any, drops every line
from that document to medium and flags it for a human. The model got this right,
but "the model got it right" is not a control. The keyword check is the control.

I take `text/plain` over the HTML alternative deliberately. Both carry the same
figures, and passing both invites the model to reconcile two copies of one
document instead of reading one carefully.

**Images.** Both scans are the Andina proforma. The low-resolution fax is mostly
legible; the glare photo has its price column wiped out across the top three
line items. The vision prompt says explicitly that null is a useful answer and a
guess is not, and on the glare scan that is exactly what comes back: items 01 to
03 have `price_per_unit` null with "obscured by glare", while 04 to 06 carry
values read from below the glare band.

Confidence from images is then **capped at low regardless of what the model
reports**. A model reading a bad photograph will tell you it is confident. It
should not be believed, and the cap is in code rather than in the prompt because
that is not something to negotiate with a model about.

One thing the fax scan shows that I would not have predicted: the price column
renders visually offset from its row, so row association has to come from item
order rather than vertical position. The model noted it. On a worse scan that is
exactly where a silent, plausible, wrong answer would come from.

**PDFs.** Text layer via pdfplumber, then the model. A PDF with no text layer is
a scan wearing a PDF costume; that is detected and flagged rather than returned
empty, though rasterising and sending it through the vision path is the obvious
fix and is not done.

## Signalling uncertainty

Three mechanisms, in increasing order of how much I trust them.

1. **Model-reported confidence**, per line item. Useful, not sufficient, and
   never allowed to raise confidence above what the source justifies.
2. **Structural facts.** A derived price is never high confidence, because the
   pack size is an assumption about what the supplier meant by "pack". An image
   is never above low. A tiered price gets flagged with the tiers spelled out.
3. **Deterministic checks.** Stated unit price cross-checked against pack price
   over pack size, with disagreement beyond 2% flagged. Plausibility bounds.
   Missing currency. These cannot be talked out of firing.

Overall confidence is deliberately a claim about **the price**, not the record.
A missing SKU is recorded against the field but does not escalate the row,
because a review queue that fills up with clean prices missing a product code is
a review queue nobody reads.

The flags are sentences, not codes. `Tiered pricing - confirm the volume band
before comparing` tells a reviewer what to do; `WARN_TIER` does not.

## What this does not do

- **No cross-document reconciliation.** Both scans are the Andina PDF, so those
  six lines appear three times, and Sanova's TLD and Mekong's Mekatri are the
  same molecule from different suppliers. The table carries all of it without
  linking any of it. This is the biggest gap. Matching on INN plus strength plus
  form would get most of the way, but deciding which of three copies of the
  Andina lines is authoritative is a judgement about source precedence, and
  guessing it silently seemed worse than leaving it visible.
- **No currency conversion.** Prices sit in USD, EUR and ZAR. Converting needs a
  rate with a date attached, and a wrong rate applied silently is worse than
  three currencies shown honestly.
- **The Andina discount column is flagged, not applied.** Unit prices there are
  list prices with a separate 3-5% discount; net is not stated. Records carry
  the list price and a note.
- **Confidence is heuristic, not calibrated.** The bands are my judgement. With
  a labelled set I would check whether "low" actually correlates with being
  wrong, and tune it.
- **Prompt injection is mitigated, not solved.** Documents come from outside and
  a PDF is a fine place to hide an instruction. Content is fenced in
  `<document>` tags and the system prompt says the fence is data, which raises
  the bar and does not clear it. The real control is that a human approves
  before anything reaches a system of record, which is the design the brief
  already assumes.
