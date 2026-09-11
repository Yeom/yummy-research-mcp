# Yummy Research MCP

- This repository owns the data service. Telegram operations live in the adjacent yummy_research project.
- Read README.md and docs/implementation/status.md before changing service contracts.
- Keep actual credentials in ignored .env; document only empty variables in .env.example.
- Never log authenticated request URLs, credential values, or raw provider error bodies.
- Keep report snapshots immutable. Historical observations first imported today must not appear known yesterday.
- Daily observation dates differ from publication/collection times. Preserve missing values and partial failures.
- Treasury defaults are 3Y, 10Y, 30Y. Rates change in bp; price changes in percent only with a positive comparison value.
- MCP returns data, not trading conclusions. News titles are discovery leads, not verified article contents.
- Run .venv/bin/python -m pytest before committing. Network tests require YUMMY_LIVE_TESTS=1.
- Do not commit state/, local charts, database files, or Telegram source material.
