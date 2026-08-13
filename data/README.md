# Data

Simulated devices replay real public wearable-signal datasets rather than
random noise, per PRD 2.2/9 ("缺乏真实设备数据，压测结果不可信").

- **WESAD** — wearable stress/affect dataset (chest + wrist RespiBAN/Empatica E4).
- **PPG-DaLiA** — PPG + activity dataset for HR estimation under real-world motion.

Both are hosted on the UCI ML Repository as plain zip files with no login or
data-use-agreement wall, so `scripts/download_datasets.sh` fetches them
directly with `curl` — no manual step required:

```bash
./scripts/download_datasets.sh              # both datasets -> data/raw/{wesad,ppg_dalia}/
./scripts/download_datasets.sh wesad         # just one
DATA_DIR=/mnt/data ./scripts/download_datasets.sh   # download elsewhere
```

**Run this on the machine that will actually run `docker compose up`, not on
your laptop.** The datasets only exist to feed the ingestion service once
it's deployed, so there's no reason to pull ~3GB down twice — provision the
cloud VM, `git clone` the repo there, and run the script (or
`infra/cloud/bootstrap_vm.sh`, which does both) directly on it. See
[infra/cloud/bootstrap_vm.sh](../infra/cloud/bootstrap_vm.sh).

The script only needs `bash`, `curl`, and `unzip` — no bash 4+ features — so
it runs the same on macOS's stock `/bin/bash` (3.2) as on an Ubuntu cloud VM.

Raw and processed data are gitignored (`data/raw/`, `data/processed/`) — never
commit dataset files to the repo.
