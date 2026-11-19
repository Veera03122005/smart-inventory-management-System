# SmartStock AI — Baseline Model Metrics Snapshot

> **Research Paper Baseline**: Pre-intervention performance snapshot evaluated on the shipped 60-day validation window.

- **Generated At**: 2026-11-19T10:04:16
- **Training Duration**: 8.8 seconds
- **Validation Horizon**: 60 days (time-based split)
- **Forecast Horizon**: 7 days
- **Cycle Service Level**: 98% (Z = 2.05)

---

## Cross-Ingredient Champion Model Overview

| Ingredient ID | Ingredient Name | Unit | Champion Model | Champion WAPE (%) | Champion MAE | Champion RMSE | Lead Time | Shelf Life |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ING01` | **Chicken** | kg | `XGBoost` | **12.08%** | 3.993 | 5.424 | 1d | 2d |
| `ING02` | **Mutton** | kg | `Random Forest` | **10.83%** | 0.854 | 1.12 | 1d | 2d |
| `ING03` | **Basmati rice** | kg | `Random Forest` | **10.24%** | 3.202 | 4.132 | 3d | 365d |
| `ING04` | **Cooking oil** | L | `XGBoost` | **11.31%** | 1.475 | 2.005 | 3d | 180d |
| `ING05` | **Onion** | kg | `XGBoost` | **11.93%** | 3.22 | 4.054 | 1d | 14d |
| `ING06` | **Tomato** | kg | `Random Forest` | **10.03%** | 1.617 | 1.998 | 1d | 5d |

---

## Per-Ingredient Model Evaluation & Data Quality

### ING01 — Chicken (kg)

- **Selected Champion Model**: `XGBoost` (Residual Std Dev $\sigma = 5.258$ kg)
- **Current Closing Stock**: 0.0 kg (as of 2026-11-15)
- **Days of Cover**: 0.0 days
- **Reorder Point ($s$)**: 53.92 kg | **Order-up-to ($S$)**: 53.92 kg

#### Data Quality & Channel Provenance

| Channel / Data Quality Category | Total Days | Proportion (%) |
| :--- | :--- | :--- |
| `entered` | 404 | 85.6% |
| `reconstructed` | 68 | 14.4% |
| **Total Observed Series Length** | **472** | **100.0%** |

#### 60-Day Validation Window Performance

| Model | WAPE (%) | MAE | RMSE | Champion? |
| :--- | :--- | :--- | :--- | :--- |
| Seasonal naive | 23.33% | 7.71 | 10.882 |  |
| Moving avg (7d) | 21.07% | 6.963 | 9.159 |  |
| Random Forest | 12.37% | 4.087 | 5.857 |  |
| XGBoost | 12.08% | 3.993 | 5.424 | ✓ Selected |

---

### ING02 — Mutton (kg)

- **Selected Champion Model**: `Random Forest` (Residual Std Dev $\sigma = 1.068$ kg)
- **Current Closing Stock**: 11.5 kg (as of 2026-11-15)
- **Days of Cover**: 1.17 days
- **Reorder Point ($s$)**: 10.78 kg | **Order-up-to ($S$)**: 10.78 kg

#### Data Quality & Channel Provenance

| Channel / Data Quality Category | Total Days | Proportion (%) |
| :--- | :--- | :--- |
| `entered` | 396 | 83.9% |
| `reconstructed` | 76 | 16.1% |
| **Total Observed Series Length** | **472** | **100.0%** |

#### 60-Day Validation Window Performance

| Model | WAPE (%) | MAE | RMSE | Champion? |
| :--- | :--- | :--- | :--- | :--- |
| Seasonal naive | 21.96% | 1.733 | 2.327 |  |
| Moving avg (7d) | 20.62% | 1.627 | 2.193 |  |
| Random Forest | 10.83% | 0.854 | 1.12 | ✓ Selected |
| XGBoost | 12.96% | 1.023 | 1.275 |  |

---

### ING03 — Basmati rice (kg)

- **Selected Champion Model**: `Random Forest` (Residual Std Dev $\sigma = 4.05$ kg)
- **Current Closing Stock**: 154.0 kg (as of 2026-11-15)
- **Days of Cover**: 4.47 days
- **Reorder Point ($s$)**: 106.51 kg | **Order-up-to ($S$)**: 370.9 kg

#### Data Quality & Channel Provenance

| Channel / Data Quality Category | Total Days | Proportion (%) |
| :--- | :--- | :--- |
| `entered` | 364 | 77.1% |
| `reconstructed` | 78 | 16.5% |
| `iot` | 30 | 6.4% |
| **Total Observed Series Length** | **472** | **100.0%** |

#### 60-Day Validation Window Performance

| Model | WAPE (%) | MAE | RMSE | Champion? |
| :--- | :--- | :--- | :--- | :--- |
| Seasonal naive | 15.74% | 4.922 | 6.478 |  |
| Moving avg (7d) | 14.35% | 4.489 | 5.873 |  |
| Random Forest | 10.24% | 3.202 | 4.132 | ✓ Selected |
| XGBoost | 12.19% | 3.814 | 4.918 |  |

---

### ING04 — Cooking oil (L)

- **Selected Champion Model**: `XGBoost` (Residual Std Dev $\sigma = 1.982$ L)
- **Current Closing Stock**: 60.5 L (as of 2026-11-15)
- **Days of Cover**: 4.59 days
- **Reorder Point ($s$)**: 42.66 L | **Order-up-to ($S$)**: 144.58 L

#### Data Quality & Channel Provenance

| Channel / Data Quality Category | Total Days | Proportion (%) |
| :--- | :--- | :--- |
| `entered` | 398 | 84.3% |
| `reconstructed` | 44 | 9.3% |
| `iot` | 30 | 6.4% |
| **Total Observed Series Length** | **472** | **100.0%** |

#### 60-Day Validation Window Performance

| Model | WAPE (%) | MAE | RMSE | Champion? |
| :--- | :--- | :--- | :--- | :--- |
| Seasonal naive | 16.29% | 2.124 | 2.751 |  |
| Moving avg (7d) | 13.8% | 1.799 | 2.414 |  |
| Random Forest | 11.49% | 1.498 | 2.013 |  |
| XGBoost | 11.31% | 1.475 | 2.005 | ✓ Selected |

---

### ING05 — Onion (kg)

- **Selected Champion Model**: `XGBoost` (Residual Std Dev $\sigma = 4.02$ kg)
- **Current Closing Stock**: 126.0 kg (as of 2026-11-15)
- **Days of Cover**: 4.23 days
- **Reorder Point ($s$)**: 33.45 kg | **Order-up-to ($S$)**: 261.33 kg

#### Data Quality & Channel Provenance

| Channel / Data Quality Category | Total Days | Proportion (%) |
| :--- | :--- | :--- |
| `entered` | 366 | 77.5% |
| `reconstructed` | 76 | 16.1% |
| `iot` | 30 | 6.4% |
| **Total Observed Series Length** | **472** | **100.0%** |

#### 60-Day Validation Window Performance

| Model | WAPE (%) | MAE | RMSE | Champion? |
| :--- | :--- | :--- | :--- | :--- |
| Seasonal naive | 15.98% | 4.312 | 5.373 |  |
| Moving avg (7d) | 14.15% | 3.818 | 4.847 |  |
| Random Forest | 12.02% | 3.245 | 4.044 |  |
| XGBoost | 11.93% | 3.22 | 4.054 | ✓ Selected |

---

### ING06 — Tomato (kg)

- **Selected Champion Model**: `Random Forest` (Residual Std Dev $\sigma = 1.953$ kg)
- **Current Closing Stock**: 0.0 kg (as of 2026-11-15)
- **Days of Cover**: 0.0 days
- **Reorder Point ($s$)**: 18.47 kg | **Order-up-to ($S$)**: 18.47 kg

#### Data Quality & Channel Provenance

| Channel / Data Quality Category | Total Days | Proportion (%) |
| :--- | :--- | :--- |
| `entered` | 402 | 85.2% |
| `reconstructed` | 70 | 14.8% |
| **Total Observed Series Length** | **472** | **100.0%** |

#### 60-Day Validation Window Performance

| Model | WAPE (%) | MAE | RMSE | Champion? |
| :--- | :--- | :--- | :--- | :--- |
| Seasonal naive | 13.14% | 2.117 | 2.629 |  |
| Moving avg (7d) | 11.34% | 1.827 | 2.243 |  |
| Random Forest | 10.03% | 1.617 | 1.998 | ✓ Selected |
| XGBoost | 10.76% | 1.734 | 2.267 |  |

---

