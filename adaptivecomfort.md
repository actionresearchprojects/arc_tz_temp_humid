# Adaptive Comfort: Acceptability Limits and Air Speed

This document records how the adaptive comfort chart's boundaries are defined, what
the ASHRAE 55 acceptability limits mean, how the elevated-air-speed allowance works,
and which decisions were taken when both were added to the dashboard in August 2026.

It is written to be read by someone who has not seen the code.

> **Method is applicable only for occupant-controlled naturally conditioned spaces that meet all of the following criteria:**
> **(a)** There is no mechanical cooling system installed. No heating system is in operation;
> **(b)** Metabolic rates ranging from 1.0 to 1.5 met; and
> **(c)** Occupants are free to adapt their clothing to the indoor and/or outdoor thermal conditions within a range at least as wide as 0.5-1.0 clo.

---

## 1. The single idea behind every comfort band

Every adaptive comfort band on the chart, whichever model is selected, has the same shape:

```
upper = (slope × running mean outdoor temp) + intercept + half-width
lower = (slope × running mean outdoor temp) + intercept - half-width
```

A centre line, and a distance either side of it. Nothing more. The models differ only
in what those three numbers are.

This matters because "80% acceptability" and "90% acceptability" are **not different
models**. They are two different half-widths around the same centre line.

---

## 2. ASHRAE 55 acceptability limits

ANSI/ASHRAE Standard 55-2020, Section 5.4.2.2, gives the 80% limits directly:

```
Upper 80% acceptability limit (°C) = 0.31 × Tpma + 21.3
Lower 80% acceptability limit (°C) = 0.31 × Tpma + 14.3
```

where `Tpma` is the prevailing mean outdoor air temperature — the x-axis of the chart.

Rearranged into the form above, that is a centre line of `0.31 × Tpma + 17.8` with a
half-width of **3.5**. The 90% limits share the same centre line with a half-width of
**2.5**.

| Level | Centre line | Half-width | Meaning |
|---|---|---|---|
| 80% | 0.31·Tpma + 17.8 | ±3.5 | 80% of occupants expected to find conditions acceptable |
| 90% | 0.31·Tpma + 17.8 | ±2.5 | 90% expected to find them acceptable — a stricter test, so a narrower band |

**80% is the compliance figure.** Section 5.4.2 states that allowable temperatures
"shall be determined from Figure 5-8 using the 80% acceptability limits", and its
informative note adds that "the 90% acceptability limits are included for information
only". The dashboard offers both, but 80% is the one to quote.

### Applicability range

Section 5.4.1(d) restricts the method to a prevailing mean outdoor temperature
**above 10 °C and below 33.5 °C**. Mkuranga sits comfortably inside that window
(see section 7); some other programme sites may not.

---

## 3. The elevated air speed allowance

Moving air makes a warm room feel cooler. ASHRAE 55 allows for this by permitting a
**higher** indoor temperature to still count as acceptable when air speed is raised.

Table 5-13 gives the allowance, relative to a baseline of 0.3 m/s:

| Average air speed | Increase in the upper limit (Δt₀) |
|---|---|
| 0.3 m/s (baseline) | — |
| 0.6 m/s | +1.2 °C |
| 0.9 m/s | +1.8 °C |
| 1.2 m/s | +2.2 °C |

Three rules govern it:

1. **It raises the upper boundary only.** The lower boundary never moves. Air movement
   cannot make a cold room comfortable.
2. **It applies only above 25 °C.** Section 5.4.2.4: "If t₀ > 25 °C, then it shall be
   permitted to increase the upper acceptability temperature limits".
3. **Only these three speeds exist.** The standard gives no basis for interpolating
   between them, which is why the dashboard uses a dropdown rather than a numeric field.

### Why the boundary steps

Because the allowance switches on at a fixed temperature rather than fading in, the
upper boundary jumps vertically at the point where it crosses 25 °C. That crossing sits at:

```
Tpma = (25 - intercept - half-width) / slope
```

which for the ASHRAE models is **11.9 °C** for the 80% band and **15.2 °C** for the 90%
band. Below those points the boundary is unchanged; above them it is raised by the full
Δt₀. This is the same discontinuity visible in the CBE Thermal Comfort Tool's adaptive
chart, and the dashboard reproduces it exactly.

The step is an artefact of the standard, not of the physics. The underlying relationship
is smooth — the benefit of air movement grows gradually with temperature, and the Δt₀
values are derived from continuous equal-SET contours. ASHRAE flattened that into an
on/off threshold and three discrete speeds so the rule could be checked simply.

### The 25 °C gate is an indoor temperature

A common misreading. `t₀` is **operative temperature** — the indoor value, the chart's
y-axis. The outdoor variable is written `Tpma`. Table 5-13's own title refers to
"Acceptable Operative Temperature Limits", and both `t₀` and `Δt₀` mean operative
temperature throughout.

So the gate is a **horizontal** threshold at y = 25 °C, not a vertical one at x = 25 °C.
The step appears at a particular position along the x-axis only because the boundary
rises with x and therefore crosses that horizontal line somewhere. The two ASHRAE bands
step at *different* x positions, which would be impossible if the gate were on outdoor
temperature.

Physically the threshold marks where a breeze stops being a nuisance and starts being
relief. Below about 25 °C you are not sweating much, so there is little evaporation for
moving air to accelerate, and the convective loss is heat you wanted to keep — a draught,
not cooling. ASHRAE treats this seriously elsewhere: Section 5.3.2.4 actively *caps* air
speed at 0.2 m/s below 23 °C.

### Which readings the allowance can affect

Only readings above 25 °C, and this follows automatically rather than needing a separate rule.

The allowance can only change the verdict for readings in the gap between the old ceiling
and the new one — anything below the old ceiling was already acceptable, anything above
the new one is still too warm. Since the ceiling is only raised where it already exceeds
25 °C, everything in that gap is above 25 °C too. A reading of 23 °C gains nothing from
the air speed setting, which is the right answer physically.

---

## 4. The Vellei et al. humidity models

The dashboard's default band comes from Vellei, Herrera, Fosas and Natarajan, *The
influence of relative humidity on adaptive thermal comfort*, Building and Environment
124 (2017) 171–185. Equations 4–6 of that paper:

```
RH > 60%        Top = 0.53 × Tout + 12.85  (±2.84)   R² = 0.84
40% < RH ≤ 60%  Top = 0.53 × Tout + 14.16  (±3.70)   R² = 0.76
RH ≤ 40%        Top = 0.52 × Tout + 15.23  (±4.40)   R² = 0.66
```

### The ± values are not acceptability percentages

This was the question that decided the interface design. The paper states that "the
temperature bands in the above equations are given by the prediction intervals", defined
as the range in which future observations fall with 0.95 probability. That is a
statistical spread around a fitted line — a different kind of quantity from "80% of people
find this acceptable".

**However, 80% acceptability is applied one step earlier.** When assembling the data, the
authors discarded any grid bin in which fewer than 80% of votes were neutral, explicitly
"in order to meet the 80% acceptability criterion incorporated in the current model". The
paper also notes that the medium-humidity band comes out equal to the acceptability range
of the ASHRAE model.

The conclusion, and the reason the dashboard's acceptability toggle applies only to the
ASHRAE bands:

> The Vellei bands are already the 80% bands. No 90% variant exists in the paper, and none
> can be derived by scaling, because the width is a prediction interval rather than a
> proportion of occupants.

### Running mean

The paper's equations are written against outdoor mean temperature, while the dashboard
supplies an exponentially weighted running mean (α = 0.8). The authors tested both
formulations and found "little difference in whether monthly mean or running mean outdoor
temperature is used in computing either adaptive model", so the substitution is sound.

### Air speed and the Vellei bands

Vellei deliberately excluded air velocity as a predictor, on the grounds that occupants
control it directly and it therefore cannot be treated as an independent variable. The
consequence is that the field data behind these bands already contains whatever fans and
open windows those occupants were using — and much of the sample comes from hot climates
where fan use is routine.

Some of the benefit of air movement is therefore probably inside the band already.
Applying the Table 5-13 allowance on top of a Vellei band risks counting the same fan
twice. The dashboard permits the combination, because it is useful for scenario work, but
warns about it in the air speed tooltip.

---

## 5. What was wrong before

The dashboard's previous "Default comfort model" was:

```
0.31 × Tpma + 17.3 ± 3.0
```

which expands to a band running from `0.31·Tpma + 14.3` to `0.31·Tpma + 20.3`. Those are
the ASHRAE **80% lower** limit and the ASHRAE **90% upper** limit — a band that exists in
no standard, pairing a permissive floor with a strict ceiling.

Because the comfort statistic defaults to "percentage below the upper boundary", every
overheating figure that model ever produced was measured against the stricter 90% line
while being presented as the default. It has been replaced by two correct entries built on
the real Section 5.4.2.2 centre line.

**Anyone comparing new figures against old should expect the 80% option to read roughly
one degree more permissive**, and therefore to report a higher percentage within comfort.

---

## 6. Decisions taken

| Decision | Choice | Reasoning |
|---|---|---|
| Replace the broken default | Two correct ASHRAE entries, 80% and 90% | 80% is the compliance limit; 90% kept because the standard publishes it as informative |
| Acceptability toggle on Vellei bands | Not offered | Their half-widths are prediction intervals, and no 90% variant exists to offer |
| Air speed input | Dropdown of the three tabulated speeds | The standard defines no values between them and no method of interpolation |
| Air speed default | 0.3 m/s | Applies no adjustment, so existing figures are unaffected unless the setting is deliberately moved |
| Air speed on Vellei bands | Permitted, with a warning | Useful for scenarios; the double-counting risk is real but is a caveat rather than a prohibition |
| Air speed scope | One value for the whole chart | Air speed moves the *boundary*, not the reading. Per-room values would make a single drawn band wrong for most loggers on it |
| Nested 80/90 display | Optional checkbox, ASHRAE only | Matches the CBE chart when wanted; Vellei has no second band to nest |
| Gate interpretation | Raise the boundary where the *unraised* boundary exceeds 25 °C | Section 5.4.2.4 is circular as written; this is the reading the CBE reference tool uses |

### Per-room air speed

This was considered and set aside. Air speed shifts the comfort boundary rather than the
measured point, so different values per room would mean several different ceilings on one
chart, and a single drawn band could not represent them.

The idea is not lost — it belongs to a future model that evaluates each reading against
its own conditions (including its own recorded humidity) instead of reading a band off a
graph. That approach has no drawn band to contradict, so per-room air speed works
naturally within it.

---

## 7. Verification

The implementation was checked against the published standard rather than against
expectations:

- Both ASHRAE boundaries reproduce the Section 5.4.2.2 equations exactly, upper and lower.
- The Table 5-13 increments are applied to the upper boundary only; the lower boundary is
  unaffected at every air speed.
- The step positions compute to **11.935 °C** and **15.161 °C**, matching the CBE tool.
- The chart and the statistics panel apply the same gate, so the picture and the reported
  percentages cannot disagree.
- The band is sampled at 80 evenly spaced points, so a step falling between two samples
  would render as a diagonal ramp. The crossing is injected into the sample array twice —
  once carrying the unelevated value, once the raised one — and the rendered vector output
  was measured to confirm a genuine vertical edge of exactly Δt₀ at exactly the computed
  crossing.
- The 80% band fully encloses the 90% band when both are drawn.

### The step will not be visible in the Tanzania data

Over the full Open-Meteo record for Mkuranga (March 2023 to August 2026), the running mean
outdoor temperature spans **23.2 °C to 28.9 °C**. Every model's crossing point sits below
that range:

| Model | Step at Tpma | Visible in Mkuranga data? |
|---|---|---|
| ASHRAE 80% | 11.9 °C | no |
| ASHRAE 90% | 15.2 °C | no |
| Vellei RH > 60% | 17.6 °C | no |
| Vellei 40–60% | 13.5 °C | no |
| Vellei RH ≤ 40% | 10.3 °C | no |

The comfort ceiling is already above 25 °C everywhere on the chart, so raising air speed
lifts the whole band uniformly with no visible step. Because that makes the rule invisible,
a dashed reference line is drawn at 25 °C whenever air speed is above baseline, to show why
the band moved. The step itself is a cool-climate feature and would only appear in a
dataset dipping below roughly 18 °C running mean.

---

## 8. Known limitations

**The chart's y-axis is air temperature; ASHRAE's is operative temperature.** Operative
temperature combines air temperature with radiant temperature, and in these buildings the
two differ — the metal roof surface has been recorded 10 °C above the air temperature
beneath it. The readings tested against these limits are therefore systematically lower
than the quantity the standard intends. Adding formal acceptability tiers makes the chart
*look* more precise without making it so. This is a property of the instrumentation, not
of the calculation.

**Air speed is assumed, never measured.** No air speed is recorded at any site. Whatever
value is selected is a scenario. It is written into the chart caption whether or not it is
the baseline, and into the exported filename when it is not, so that two exports cannot be
mistaken for one another.

**The air speed allowance is likely optimistic in humid conditions.** Δt₀ is derived
assuming ordinary humidity. In humid air, sweat evaporates less readily, so a breeze cools
less than the table implies. For coastal Tanzania the true benefit of 1.2 m/s is probably
below +2.2 °C.

**The double-counting caveat on the Vellei bands is documented, not resolved.** See
section 4.

---

## 9. Sources

- ANSI/ASHRAE Standard 55-2020, *Thermal Environmental Conditions for Human Occupancy* —
  Sections 5.3.2.4, 5.4.1, 5.4.2, 5.4.2.2, 5.4.2.4; Figure 5-8; Table 5-13.
- M. Vellei, M. Herrera, D. Fosas, S. Natarajan, "The influence of relative humidity on
  adaptive thermal comfort", *Building and Environment* 124 (2017) 171–185.
  <https://doi.org/10.1016/j.buildenv.2017.08.005>
- CBE Thermal Comfort Tool, Center for the Built Environment, University of California
  Berkeley — used as the reference implementation for the adaptive chart.
