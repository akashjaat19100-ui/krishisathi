# 🌱 KrishiSathi (कृषि साथी / कृषी साथी)
### Tiered Irrigation & Crop-Disease Advisory Service for Small and Marginal Farmers in India

KrishiSathi is a working, demo-ready prototype web application designed for small and marginal farmers in India.
It runs locally with a single command and has zero paid API dependencies.

For complete documentation, viva preparation notes, mathematical derivations, and architecture details, see:
👉 **[docs/README.md](docs/README.md)** and **[docs/demo_script.md](docs/demo_script.md)**.

---

## ⚡ Quick Start

```bash
# Start the application (auto-seeds 8 farmers, 2 clusters, 14 days weather)
./run.sh
# or:
python run.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

To run the unit test suite:
```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/ -v -s
```
