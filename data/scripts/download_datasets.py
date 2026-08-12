"""Placeholder for dataset setup (PRD 2.2/9): WESAD and PPG-DaLiA.

Neither dataset can be fetched with a plain HTTP GET — both are hosted behind
a data-use agreement. This script documents where to get them; it doesn't
download anything itself.

WESAD:      https://archive.ics.uci.edu/dataset/465/wesad+wearable+stress+and+affect+detection
PPG-DaLiA:  https://archive.ics.uci.edu/dataset/495/ppg+dalia

After downloading and extracting manually, place the contents under:
  data/raw/wesad/
  data/raw/ppg_dalia/
"""

if __name__ == "__main__":
    print(__doc__)
