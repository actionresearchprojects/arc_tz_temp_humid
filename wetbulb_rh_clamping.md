# Why We Clamp RH to 99% for the Wet Bulb Calculation

## The short version

Some sensors report humidity values of exactly 100%. This is the sensor hitting its ceiling - it cannot read higher, so it pegs at 100.0%. In reality the air may be fully saturated or close to it, but the sensor cannot distinguish between 99.5% and 100% and just reports 100.

The Stull (2011) formula we use to calculate wet bulb temperature was only tested up to 99% RH. At 100% it gives a result 0.07°C above what physics says it should be - tiny, but technically outside the validated range.

So instead of either:
- **Ignoring those readings** (creating gaps in the wet bulb line during the wettest, hottest periods - exactly when wet bulb matters most), or
- **Feeding 100% straight into the formula** (getting a result 0.07°C off, which is smaller than the formula's own stated accuracy anyway)

…we **clamp** the humidity to 99% before calculating. The difference in the result is negligible.

---

## What the data actually looks like

Checking the raw sensor data, TinyTag loggers never report above exactly 100.0% - they hard-cap there. There are no readings of 101%, 103% etc. The distribution is:

- A small tail of readings in the 99-100% range (sensor approaching saturation)
- A large cluster **exactly at 100.0%** (sensor pegged at its ceiling)

So the only case we are handling is: sensor reports 100.0%, we treat it as 99% for the calculation.

---

## Why clamping to 99% is the right answer

At very high humidity, wet bulb temperature and dry bulb temperature converge - when the air is fully saturated (100% RH), no evaporative cooling is possible, so the wet bulb equals the dry bulb. The numbers:

| Input | Stull result | Physical truth | Error |
|-------|-------------|----------------|-------|
| T = 30°C, RH = 99% | Tw = 29.97°C | ≈ 30.00°C | 0.03°C |
| T = 30°C, RH = 100% (clamped to 99%) | Tw = 29.97°C | 30.00°C | 0.03°C |

The sensor is telling us the air is saturated. We agree. Clamping to 99% gives a result 0.03°C below the physical truth - well within the formula's own ±0.3°C accuracy, and well within sensor noise.

If we fed 100% directly into Stull without clamping, we would get Tw = 30.07°C - only 0.07°C off. It would not produce nonsense in this dataset. We clamp anyway because 100% is outside the validated range and the correct physical answer is known (Tw ≈ T), so treating it as 99% is the more honest approach.

---

## What "valid range 5-99%" actually means

The Stull formula is a curve fitted to data. The author tested it against real psychrometric readings between 5% and 99% RH and found it accurate to ±0.3°C within that range. It is not like a formula that only works inside certain limits and then breaks - it is a smooth polynomial that continues to produce numbers outside those limits, those numbers just haven't been validated.

At the low end (below 5% RH), the formula degrades more unpredictably, so those readings are shown as gaps. In this dataset, no sensor ever reads below 5% RH, so this guard never fires in practice.

---

## In the code

```javascript
function stullWetBulb(T, RH) {
  if (T < -20 || T > 50 || RH < 5) return null;  // gap - genuinely out of range
  if (RH > 99) RH = 99;  // sensor saturation artefact - clamp to valid ceiling
  return T * Math.atan(0.151977 * Math.pow(RH + 8.313659, 0.5))
    + Math.atan(T + RH)
    - Math.atan(RH - 1.676331)
    + 0.00391838 * Math.pow(RH, 1.5) * Math.atan(0.023101 * RH)
    - 4.686035;
}
```

Temperature out of range → gap (return null, shows as break in line).  
RH below 5% → gap.  
RH above 99% (in practice: exactly 100.0%) → clamp to 99%, calculate normally.
