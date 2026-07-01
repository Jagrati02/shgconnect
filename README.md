# SahayogBazaar

**An adaptive K-Means clustering framework that helps women-led Self-Help Groups (SHGs) collectively fulfil bulk market demand.**

SahayogBazaar is a Django marketplace integrated with a machine-learning framework for
**collaborative order fulfilment** among SHGs. Individually, most SHGs are too small to take on
large institutional or bulk orders. SahayogBazaar clusters similar SHGs by livelihood and
production capacity, then uses a **proportional capacity-based allocation** strategy to split one
bulk order fairly across a whole cluster — so groups that could never win a large order alone can
fulfil it together.

This repository is the reference implementation for the research paper *“SahayogBazaar: An
Adaptive K-Means Clustering Framework for Bridging Women-Led Self-Help Groups with Bulk Market
Demand.”*

---

## Key Features

- **Two-sided marketplace** — SHGs list products; buyers browse and place bulk orders.
- **Search & filters** — full-text search (product, SHG, category, state) plus category,
  geographic (state), and price filters.
- **Order lifecycle** — `PENDING → CONFIRMED → SHIPPED → DELIVERED / CANCELLED`, with real-time
  stock validation, stock restoration on cancellation, reorder, and reviews.
- **K-Means clustering** — ~51k SHGs across 18 states grouped into 10 livelihood clusters
  (offline-trained, database-served).
- **Proportional allocation** — routes a bulk order to the matching cluster and splits it by
  capacity: `Aᵢ = (Cᵢ / ΣCⱼ) × Q`. Placed cluster orders are persisted and viewable.
- **Cluster ↔ profile linking** — registered SHGs are matched to their dataset cluster on import.
- **Role-based dashboards** — SHG and buyer dashboards with real revenue/order/cluster data and charts.

## Tech Stack

- **Backend:** Django 6.0.3 (Model-View-Template, server-rendered)
- **Database:** SQLite (development)
- **ML / data (offline, notebooks + seeding):** scikit-learn, pandas, NumPy, Matplotlib, seaborn
- **Images:** Pillow · **Excel:** openpyxl

The web server itself needs only Django + Pillow + openpyxl; the ML stack is used offline
(notebooks and the demo-seed image generator), never at request time.

## Repository Structure

```
shgconnect/
├─ backend/                     # Django project (run manage.py from here)
│  ├─ core/                     # home page
│  ├─ users/                    # SHGProfile, BuyerProfile, auth, dashboards
│  ├─ products/                 # Product, Category, marketplace
│  ├─ orders/                   # Order, OrderItem, order lifecycle
│  ├─ clusters/                 # clusters, allocation engine, cluster orders
│  │  ├─ allocation.py          # proportional allocation framework
│  │  └─ management/commands/   # import_clusters, seed_marketplace
│  ├─ templates/  static/  media/
│  └─ er_diagram.png
├─ data/                        # datasets + generated figures
├─ notebooks/                   # ML notebooks (clustering, evaluation)
└─ requirements.txt
```

## Getting Started

### 1. Install dependencies
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Set up the database and demo data
```bash
cd backend
python manage.py migrate
python manage.py seed_marketplace                                   # demo SHGs + products (with images)
python manage.py import_clusters --csv ../data/cluster_results.csv  # load clusters + link SHGs
```

### 3. Run the server
```bash
python manage.py runserver
```
Open http://127.0.0.1:8000/.

### Demo logins
Seeded SHG accounts (password **`demo12345`**):
`dairy@`, `grains@`, `crafts@`, `orchard@`, `fishery@` `demo.shgconnect`.
Create a buyer account via **Sign up** to browse and place orders.

## Machine-Learning Pipeline

Clustering is trained **offline** and served from the database:

1. `notebooks/shg_data_synthesis.ipynb` — generates a multi-state dataset from real Assam records.
2. `notebooks/shg_clustering.ipynb` — feature engineering + K-Means. Final model: **K = 10**,
   Silhouette **0.5755**, Davies-Bouldin **0.3707**. Outputs `data/cluster_results.csv`.
3. `python manage.py import_clusters --csv ../data/cluster_results.csv` — loads clusters and
   members, and links registered SHG profiles to their cluster.

**Feature-engineering insight:** domain-driven features (one-hot primary livelihood weighted ×2 +
MinMax-scaled numerics) lifted the Silhouette score from 0.161 to 0.576.

### Evaluation notebooks
- `notebooks/algorithm_comparison.ipynb` — K-Means vs GMM vs DBSCAN.
- `notebooks/allocation_simulation.ipynb` — proportional vs greedy allocation (fulfilment 0.63 → 0.87).

## Proportional Allocation

Reachable from any cluster-enabled product’s **Place Order** page:
`/clusters/allocate/<product_id>/?quantity=N` (preview) and `.../place/` (commit).

1. **Route** the order to the cluster whose dominant livelihood matches the product.
2. **Direct** — if a single SHG has capacity ≥ Q, assign it the whole order.
3. **Proportional** — otherwise split by capacity so the shares always sum to Q.

Placed cluster orders are stored (`ClusterOrder` / `ClusterOrderAllocation`) and listed at
`/clusters/orders/`. This is separate from the normal single-SHG order flow, which is left intact.

## Management Commands

| Command | Purpose |
|---------|---------|
| `import_clusters --csv <path>` | Load clusters/members from CSV and link registered SHGs. Pass `--clear` to reset. |
| `seed_marketplace [--fresh]` | Create demo SHGs + products with generated images. |

> Note: always pass `--csv` to `import_clusters` (the default path resolution is unreliable).

## Roadmap / Future Work

Not yet implemented (aligned with the paper’s stated future work):
- Demand forecasting (Prophet / LSTM time-series)
- Real-time payment gateway
- Geolocation-based recommendations (Haversine distance)
- Mobile application and ONDC interoperability
- Validation on real multi-state NRLM data

## Production Notes

The project ships with development settings (`DEBUG=True`, SQLite, console email, hardcoded
`SECRET_KEY`). Harden settings, move secrets to environment variables, and switch to PostgreSQL
before any deployment.

## Authors

Jagrati Pareek · Gargi Gupta · Garima Garg — Swami Keshvanand Institute of Technology (SKIT), Jaipur.
