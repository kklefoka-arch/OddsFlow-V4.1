# League Configuration — 29 Active Leagues

Source: `fetch_upcoming.py` ACTIVE_LEAGUES (authoritative). Updated 2026-06-08.
`sportmonks_id` is the key used in all API calls and DB lookups.
USL League Two (797) removed 2026-05-29 — dropped from Sportmonks subscription.
Big 5 EU (PL 8, Ligue 1 301, La Liga 564, Serie A 384, La Liga 2 567) never in active set.

Tier split for engine analysis: **T1+T2 vs T3** (country-context tiers, not Sportmonks tiers).

---

## Tier 1 — 16 leagues (top flight of their country)

| Country | League | Sportmonks ID |
|---------|--------|--------------|
| Sweden | Allsvenskan | 573 |
| Norway | Eliteserien | 444 |
| Iceland | Besta deild | 345 |
| Finland | Veikkausliiga | 292 |
| Republic of Ireland | Premier Division | 360 |
| United States | Major League Soccer | 779 |
| Brazil | Serie A | 648 |
| Japan | J1 100 Year Vision League | 3537 |
| South Korea | K League 1 | 1034 |
| China | Super League | 989 |
| Bolivia | Liga De Futbol Prof | 1098 |
| Ecuador | Liga Pro | 696 |
| Canada | Premier League | 1689 |
| Estonia | Meistriliiga | 286 |
| Kazakhstan | Premier League | 393 |
| Lithuania | A Lyga | 405 |

---

## Tier 2 — 6 leagues (division directly below top flight)

| Country | League | Sportmonks ID |
|---------|--------|--------------|
| Sweden | Superettan | 579 |
| Colombia | Primera B | 678 |
| Finland | Ykköseliga | 295 |
| Estonia | Esiliiga A | 289 |
| United States | USL Championship | 791 |
| Japan | J2/J3 100 Year Vision League | 3550 |

---

## Tier 3 — 7 leagues (lower tiers + cups)

| Country | League | Sportmonks ID |
|---------|--------|--------------|
| Argentina | Reserve League | 1642 |
| Iceland | 2. Deild | 351 |
| United States | USL League One | 1607 |
| United States | MLS Next Pro | 2545 |
| Sweden | Ettan: North | 585 |
| Sweden | Ettan: South | 588 |
| Colombia | Copa Colombia | 681 |

---

## Notes

- Tier split for Foundation Matrix: `all` / `t1t2` / `t3` (T1+T2 combined vs T3)
- `fetch_upcoming.py` ACTIVE_LEAGUES is the **authoritative source** — update it when subscription changes, then update this doc
- USL League Two (797) removed 2026-05-29; historical fixtures remain in DB under that league_id
- `fetch_upcoming.py` max_pages: July–Oct = 30, other months = 20
