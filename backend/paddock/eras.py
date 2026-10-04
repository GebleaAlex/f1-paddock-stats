"""Regulation eras of the world championship, by engine formula and the biggest technical rule changes.

Written from the published technical regulations, in our own words. The years are inclusive.
"""

ERAS = [
    {
        "id": "1950",
        "from": 1950,
        "to": 1953,
        "name": "Pre-war machinery",
        "engine": "4.5 litre naturally aspirated or 1.5 litre supercharged",
        "summary": "Front-engined cars, many of them pre-war designs; Alfa Romeo then Ferrari dominate.",
    },
    {
        "id": "1954",
        "from": 1954,
        "to": 1960,
        "name": "2.5 litre",
        "engine": "2.5 litre naturally aspirated or 0.75 litre supercharged",
        "summary": "Mercedes, Maserati and Ferrari; by the end Cooper's mid-engined cars change car design for good.",
    },
    {
        "id": "1961",
        "from": 1961,
        "to": 1965,
        "name": "1.5 litre",
        "engine": "1.5 litre naturally aspirated",
        "summary": "Small engines; monocoque chassis arrive with the Lotus 25.",
    },
    {
        "id": "1966",
        "from": 1966,
        "to": 1976,
        "name": "3 litre",
        "engine": "3 litre naturally aspirated or 1.5 litre supercharged",
        "summary": "The Cosworth DFV powers most of the grid; wings appear from 1968.",
    },
    {
        "id": "1977",
        "from": 1977,
        "to": 1988,
        "name": "Ground effect and turbos",
        "engine": "3 litre naturally aspirated or 1.5 litre turbocharged",
        "summary": "Ground effect from 1977, flat bottoms from 1983, turbo engines dominate the mid-1980s.",
    },
    {
        "id": "1989",
        "from": 1989,
        "to": 1994,
        "name": "3.5 litre",
        "engine": "3.5 litre naturally aspirated (turbos banned)",
        "summary": "V10s and V12s; active suspension and electronic aids until their ban for 1994.",
    },
    {
        "id": "1995",
        "from": 1995,
        "to": 2005,
        "name": "3 litre V10",
        "engine": "3 litre naturally aspirated, V10 from 2000",
        "summary": "Grooved tyres from 1998, refuelling strategy races, the Schumacher-Ferrari years.",
    },
    {
        "id": "2006",
        "from": 2006,
        "to": 2013,
        "name": "2.4 litre V8",
        "engine": "2.4 litre V8, KERS hybrid boost from 2009",
        "summary": "Engine freeze, slick tyres and narrow wings from 2009, no refuelling from 2010, DRS from 2011.",
    },
    {
        "id": "2014",
        "from": 2014,
        "to": 2021,
        "name": "Turbo hybrid",
        "engine": "1.6 litre V6 turbo with energy recovery from heat and braking",
        "summary": "Mercedes dominates; wider, faster cars from 2017.",
    },
    {
        "id": "2022",
        "from": 2022,
        "to": 2025,
        "name": "Ground effect returns",
        "engine": "1.6 litre V6 turbo hybrid",
        "summary": "Venturi floors to let cars follow closely; 18-inch wheels.",
    },
    {
        "id": "2026",
        "from": 2026,
        "to": None,
        "name": "Active aero and 50/50 power",
        "engine": "1.6 litre V6 turbo, about half the power electric, sustainable fuel, no MGU-H",
        "summary": "Smaller, lighter cars with movable wings; energy management decides lap times.",
    },
]


def era_for(year: int) -> dict | None:
    for e in ERAS:
        if e["from"] <= year and (e["to"] is None or year <= e["to"]):
            return e
    return None
