# DayLight Metrics Calculation Documentation

This document details the exact calculations and methodologies used to derive the vital signs and cognitive load metrics in the DayLight application.

## 1. Raw Metrics (Ingested from Presage SmartSpectra SDK)

The metrics are extracted from the `presage_daemon` (C++), which interfaces directly with the SmartSpectra SDK.

| Metric | Source | Description |
| :--- | :--- | :--- |
| **Pulse Rate** | `metrics.pulse().rate()` | Current heart rate in beats per minute (BPM). |
| **Pulse Confidence** | `metrics.pulse().rate().confidence()` | SDK's confidence level (0.0 - 1.0) in the pulse measurement. |
| **Breathing Rate** | `metrics.breathing().rate()` | Current respiratory rate in breaths per minute (BPM). |
| **Breathing Confidence** | `metrics.breathing().rate().confidence()` | SDK's confidence level (0.0 - 1.0) in the breathing measurement. |
| **Pulse Trace (PPG)** | `metrics.pulse().trace()` | Raw photoplethysmogram (PPG) signal reflecting blood volume changes. |
| **Breathing Amplitude** | `metrics.breathing().amplitude()` | Estimated depth of each breath over time. |
| **Apnea Detected** | `metrics.breathing().apnea()` | Boolean flag indicating a detected cessation of breathing. |
| **Blinking / Talking** | `metrics.face()` | Boolean flags indicating facial activity that might affect PPG quality. |

---

## 2. Derived Metrics (Calculated in Python Backend)

The backend processes the raw SDK metrics through the `cognitive_load` service to produce user-centric scores.

### 2.1 Heart Rate Variability (HRV)
HRV is the primary indicator of the balance between the sympathetic (stress) and parasympathetic (recovery) nervous systems.

**Calculation Method: RMSSD (Peak Detection)**
1.  **Peak Detection**: Identifies local maxima in the raw **Pulse Trace (PPG)**. A peak is validated if it exceeds the mean signal value to filter noise.
2.  **RR Intervals**: Calculates the time difference between successive peaks in milliseconds ($RR_i$).
3.  **RMSSD Calculation**:
    $$RMSSD = \sqrt{\frac{1}{N-1} \sum_{i=1}^{N-1} (RR_{i+1} - RR_i)^2}$$
4.  **HRV Mapping**: The RMSSD value is mapped to a 20-80 score.
    *   $RMSSD \approx 20ms \rightarrow Score: 20$
    *   $RMSSD \approx 100ms \rightarrow Score: 80$

### 2.2 Component Scores (0-100)
Each vital sign is scored against optimized "Flow" ranges.

*   **Breathing Score**: Optimal range is **12-16 BPM**.
    *   Penalties are applied if the rate drops below 10 or exceeds 18 BPM.
*   **Pulse Score**: Optimal range is **60-80 BPM**.
    *   Penalties are applied if the rate drops below 50 or exceeds 90 BPM.
*   **HRV Score**:
    $$Score = \min(100, HRV \times 1.5)$$

### 2.3 Focus Score (0-100)
The Focus Score represents the user's current level of mental clarity and physiological "Flow."

**Weighted Formula:**
$$Focus = (0.35 \times Breathing_{Score}) + (0.25 \times Pulse_{Score}) + (0.40 \times HRV_{Score})$$

*   *Note: HRV is weighted highest as it is the most robust objective indicator of cognitive state.*

### 2.4 Stress Level (0-100)
The Stress Level measures physiological arousal and "Debt" accumulation.

**Formula:**
$$Stress = (100 - Focus) + Penalties$$

**Penalties:**
*   **Breathing Penalty**: +3 points per BPM over 20 BPM.
*   **Pulse Penalty**: +2 points per BPM over 100 BPM.
*   **Apnea Penalty**: +15 points if apnea is detected.

---

## 3. Economic Impact (Budget Integration)

The Stress Level is directly converted into "Cognitive Load Points" that impact the daily and weekly budget.

### 3.1 Cognitive Cost Delta
Calculates the point adjustment for a specific reading:
$$Cost_{\Delta} = \text{round}\left(\frac{Stress}{100} \times 6\right)$$

### 3.2 Session Impact (Actual Cost)
At the end of a Sage session, the final cost of the task/event is updated:
$$Actual\_Cost = Estimated\_Cost + \text{median}(Cost_{\Delta\_history})$$

Using the **median** of all deltas recorded during the session ensures that momentary stress spikes (like a sudden noise or distraction) don't unfairly skew the entire task's impact on the user's budget.
