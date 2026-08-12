# Data

Simulated devices replay real public wearable-signal datasets rather than
random noise, per PRD 2.2/9 ("缺乏真实设备数据，压测结果不可信").

- **WESAD** — wearable stress/affect dataset (chest + wrist RespiBAN/Empatica E4).
- **PPG-DaLiA** — PPG + activity dataset for HR estimation under real-world motion.

Both require accepting a data-use agreement on their respective host sites —
`scripts/download_datasets.py` is a placeholder that documents where to get
each one and where to place the extracted files; it does not fetch them
automatically.

Raw and processed data are gitignored (`data/raw/`, `data/processed/`) — never
commit dataset files to the repo.
