# External Agricultural Datasets

This directory holds official external reference datasets filled in manually by the user or researchers.

---

## 1. District Wheat Yield (`district_yield_wheat.csv`)

This file records historical district-level wheat statistics for the target district(s).

### Column Definitions:
- `district`: District name matching plot records (e.g., `Anand`).
- `season`: Cropping season in standard `YYYY-YY` format (e.g., `2021-22`).
- `area_ha`: Cultivated area in hectares ($> 0$).
- `production_tonnes`: Total district production in metric tonnes ($> 0$).
- `yield_kg_per_ha`: District average yield in kilograms per hectare ($> 0$). Note: $\text{yield} \approx \frac{\text{production} \times 1000}{\text{area}}$. Expected range for wheat is roughly 500 to 6000 kg/ha.
- `source_name`: Official agency or report name (e.g., `DES Gujarat Directorate of Agriculture`, `DAC&FW APY`).
- `source_url`: URL or document citation.
- `retrieved_on`: Date of manual retrieval in `YYYY-MM-DD` format.

> **Important**: Never scrape websites automatically. Fill this file by hand from verified official government statistics.

