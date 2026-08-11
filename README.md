<p align="center">
  <img src="farewise_logo.svg" alt="FareWise logo" width="75%">
</p>

## 🚇 Turn TfL journey history into future fare savings

FareWise is a Transport for London (TfL) fare optimisation tool that analyses journey history to find the cheapest payment option. It currently supports London Underground, Overground and DLR journeys only, with support for other TfL modes planned for later.

To use FareWise, download a TfL journey history CSV from your Oyster or contactless account and pass it to farewise.py:

```bash
python farewise.py journey_history.csv
```

## How the comparison works

FareWise compares PAYG (Pay as you go) with Travelcard-based options using TfL’s published fare information from the [TfL fares page](https://tfl.gov.uk/fares/new-fares).

FareWise compares:

```text
PAYG only
Zone  1   Travelcard + PAYG outside Zone  1
Zones 1–2 Travelcard + PAYG outside Zones 1–2
Zones 1–3 Travelcard + PAYG outside Zones 1–3
Zones 1–4 Travelcard + PAYG outside Zones 1–4
Zones 1–5 Travelcard + PAYG outside Zones 1–5
Zones 1–6 Travelcard
```

For each zone range, it tests non-annual Travelcard durations:

```text
1 Day Anytime
1 Day Off-Peak
7 Day
Monthly
```

Date-based payment options are then tested across the journey history. For example, a 7 Day Travelcard could start on different days, so FareWise checks each possible 7-day window and calculates the total cost.

Finally, FareWise selects the lowest-cost result and reports which option would have been cheapest.