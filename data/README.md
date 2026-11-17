# Data

Everything in this folder is **fictional**: names, prices, phone numbers, bookings and policies were
invented for this project and will be replaced with real information later. No real guest data is
stored here.

- `kb/` is the knowledge base the assistant retrieves from (RAG). Written in English; the
  multilingual embedding model matches Italian and German questions against it.
- `structured/` is the source of truth for the tools:
  - `rooms.yaml`: units, capacity, nightly prices per season
  - `seasons.yaml`: season calendar, winter closure, minimum stays, fees and policy numbers
  - `availability.json`: existing bookings and exclusive-use periods (events)

When you change a price, fee or policy number, update both `structured/` and the matching sentence
in `kb/`. `tests/test_data_consistency.py` fails if they disagree.
