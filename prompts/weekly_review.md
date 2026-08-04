# WEEKLY REVIEW — the learning loop

Follow CLAUDE.md. This is the substantive weekly session. Steps:

1. Read `journal.md` and `state/positions.json` in full.
2. **Score decisions vs outcomes separately.** A good decision can lose; a bad decision
   can win. Grade the *process*, then the result, and note where they diverged.
3. Update the running edge estimate: trades logged, win rate, average win/loss, implied
   Kelly. Compute via python3. If total logged trades < 50, restate explicitly that the
   edge estimate is noise and sizing stays suppressed.
4. **Kill list:** which setups have stopped working? Cut them. Which are working? Note
   whether to press within the caps.
5. Sleeve audit: is the barbell still ~80/20? Has the moonshot sleeve been refilled from
   anything other than realized profits? (It must not be.)
6. Correlation audit: are any "separate" positions actually the same bet? Mega-cap beta
   counts as ONE position against the cap.
7. Regime check: has anything in the DRL risk-regime read changed (refinancing stress,
   consumer, rates, AI circularity)? Propose charter amendments if so — do not silently
   drift.
8. Tempo audit: how loaded was the pipeline this week (proposals written / approved /
   executed / pruned)? Was speed lost to underwriting done too late, or edge lost to
   proposals written too loose?
9. Write the review into `journal.md` under a dated `## Weekly Review` heading.
