# 01 — Principles & Survival Math
*The reasoning behind the charter. Read once; the charter is what binds.*

---

## The 10-point operating constitution

1. **Survive first.** Avoid permanent capital loss above all. *(Buffett, Burry, Li Lu, Simons' risk monitoring.)*
2. **Edge, then size.** Only act on a defined, repeatable, statistically- or fundamentally-grounded edge. No edge → no trade. *(Simons.)*
3. **Downside before upside.** Quantify max loss before entry, before stating the upside. *(Burry, Munger's inversion.)*
4. **Asymmetry.** Small capped loss, large upside. *(Taleb, Burry.)*
5. **Many uncorrelated small bets beat one big bet.** *(Simons, Taleb.)*
6. **Circle of competence.** Trade only what the system can actually model; know the boundary. *(Buffett, Munger, Li Lu.)*
7. **Fat-pitch discipline.** Inaction is a position. Swing rarely, and hard, only in the sweet spot. *(Li Lu.)*
8. **Invert.** Every idea gets a pre-mortem: "how does this blow up?" *(Munger.)*
9. **Process over narrative.** Don't override the system with a story. *(Simons.)*
10. **Journal + review is the real moat.** Edge comes from disciplined testing and learning, not from any one call. *(Simons, Munger's checklists.)*

---

## Position sizing — the part that decides everything

**Kelly criterion:** `f* = (b·p − q) / b` where `p` = win probability, `q = 1−p`, `b` = win/loss payoff ratio.

Hard-coded facts:

- **Full Kelly is too aggressive for real trading.** It produces 50–80% drawdowns, and if you overestimate your edge it guarantees eventual ruin.
- **Fractional Kelly (¼ to ½) is the professional standard.** Half-Kelly retains ~75% of the growth rate at roughly half the drawdown. Quarter-Kelly drives risk-of-ruin toward zero *for a strategy with genuine edge.*
- **With fewer than 50–100 trades of history, the edge estimate is basically noise.** A 5-point error in win rate can swing the Kelly fraction ~3x. Early on, size *smaller* than the math suggests.
- **The 1–2% rule.** Professionals rarely risk more than 1–2% of capital per trade. That is the point-of-ruin firewall.
- **Scale size down as volatility rises** (ATR-based sizing).
- **Risk of ruin rises explosively with per-trade risk.** At very high per-trade risk, ruin approaches certainty. This is arithmetic, not caution — it is the reason a "bet it all" instruction cannot be implemented literally.

**Where the aggression actually goes:** into *how asymmetric each bet is* and *how many shots you take* — not into betting the account on one flip. That is how a small edge compounds into a large number.

---

## The barbell architecture

**CORE SLEEVE (~80%) — the compounding engine**
Buffett / Li Lu / Munger governed: quality, margin of safety, fat-pitch entries. Concentration is allowed; survival is not negotiable. Fractional-Kelly-lite sizing, capped as a small % of *total* portfolio per position.

**MOONSHOT SLEEVE (~20%) — the convexity engine**
Taleb / Burry governed: many small bets with capped downside and large convex upside. Losses are the expected case for most individual shots. The sleeve is refilled **only from realized profits**, never topped up from the core.

Nothing sits in the mediocre middle — no medium-conviction, medium-size positions that carry core-level risk with moonshot-level uncertainty.

---

## Honest expectations

This framework improves your odds and your process. It cannot manufacture a 500x. The single biggest determinant of whether a small account survives is **position sizing**, not stock-picking — get sizing right and everything else has room to work.

If you want to prove the process before risking real capital, run it in paper/simulation long enough to get a real edge estimate, then let the *measured* edge set the size.
