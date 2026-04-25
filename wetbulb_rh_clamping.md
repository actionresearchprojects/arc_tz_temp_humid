# Why We Clamp RH to 99% for the Wet Bulb Calculation

## The short version

Some sensors report humidity values above 100% (e.g. 101%, 103%). This is physically impossible — you can't have more than 100% relative humidity — so those readings are a sensor artefact, not real data. The sensor has hit its maximum and is reporting noise around that ceiling.

The Stull (2011) formula we use to calculate wet bulb temperature was only tested up to 99% RH. When you feed it a value above that, it starts producing results that are physically wrong — specifically, it can give a **wet bulb temperature higher than the dry bulb temperature**, which is impossible in nature.

So instead of either:
- **Ignoring those readings** (creating gaps in the wet bulb line during the wettest, hottest periods — exactly when wet bulb matters most), or
- **Feeding the bad number straight into the formula** (getting nonsense results like Tw > T)

…we **clamp** the humidity to 99% before calculating. This means: if the sensor says 103%, we treat it as 99% for the purpose of this calculation.

---

## Why clamping to 99% is the right answer

At very high humidity, wet bulb temperature and dry bulb temperature converge — when the air is fully saturated (100% RH), no evaporative cooling is possible, so the wet bulb equals the dry bulb. The maths bears this out cleanly:

| Input | Stull result | Physical truth | Error |
|-------|-------------|----------------|-------|
| T = 30°C, RH = 99% | Tw = 29.97°C | ≈ 30.00°C | 0.03°C |
| T = 30°C, RH = 100% | Tw = 30.07°C | 30.00°C | 0.07°C |
| T = 30°C, RH = 105% | Tw = 30.85°C | 30.00°C | **0.85°C wrong, and above T** |

Clamping 103% → 99% gives Tw ≈ 29.97°C. The physically correct answer (for a sensor that is actually saturated at 100%) is Tw = 30.00°C. That is a 0.03°C difference — well within the ±0.3°C accuracy of the formula itself, and well within sensor noise.

In other words: the sensor is telling us the air is saturated. We agree. We calculate accordingly. The tiny difference between "99%" and "100%" in the formula output is smaller than the measurement error of the sensor in the first place.

---

## What "valid range 5–99%" actually means

The Stull formula is a curve fitted to data. The author tested it against real psychrometric readings between 5% and 99% RH and found it accurate to ±0.3°C within that range. It is not like a formula that only works inside certain limits and then breaks — it is a smooth polynomial that continues to produce numbers outside those limits. The problem is that those numbers haven't been validated, and as shown above, at high RH the formula starts to diverge from physical reality.

At the low end (below 5% RH), the formula degrades more unpredictably, so those readings are shown as gaps.

At the high end (above 99% RH), the formula is still close — the divergence is small and predictable — but the sensor readings themselves are already untrustworthy (they are reporting an impossible value). Clamping to 99% is the correct treatment for both problems at once.

---

## In the code

```javascript
function stullWetBulb(T, RH) {
  if (T < -20 || T > 50 || RH < 5) return null;  // gap — genuinely out of range
  if (RH > 99) RH = 99;  // sensor saturation artefact — clamp to valid ceiling
  return T * Math.atan(0.151977 * Math.pow(RH + 8.313659, 0.5))
    + Math.atan(T + RH)
    - Math.atan(RH - 1.676331)
    + 0.00391838 * Math.pow(RH, 1.5) * Math.atan(0.023101 * RH)
    - 4.686035;
}
```

Temperature out of range → gap (return null, shows as break in line).  
RH below 5% → gap.  
RH above 99% → clamp to 99, calculate normally.
