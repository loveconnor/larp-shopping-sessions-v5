import datetime
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import duckdb

root = Path(os.environ["RUNNER_TEMP"])
seeds = list(map(int, os.environ["SEED_LIST"].split(",")))
labels = ("ranked", "candidate", "control")
medians = {label: [] for label in labels}
cpus = sorted(os.sched_getaffinity(0))[:8]
cpuset = ",".join(map(str, cpus))
print(f"Runner CPUs {cpuset}, {len(cpus)} program workers, 12 GiB container cap", flush=True)

def timestamp(value):
    return datetime.datetime.fromisoformat(value.removesuffix("Z")[:26] + "+00:00")

def elapsed(label, output, scratch):
    cmd = ["docker", "create", "--cpuset-cpus", cpuset, "--memory", "12g",
           "--memory-swap", "12g", "--network", "none", "--read-only",
           "--user", "1000:1000", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m", "-e", f"NCPU={len(cpus)}", "-e", "MEM_GB=24",
           "-e", "DATA_DIR=/data", "-e", "OUTPUT_DIR=/output", "-e", "SCRATCH_DIR=/scratch",
           "-e", "HOME=/scratch", "-v", f"{root}/data:/data:ro", "-v", f"{output}:/output",
           "-v", f"{scratch}:/scratch", label]
    container = subprocess.check_output(cmd, text=True).strip()
    try:
        subprocess.run(["docker", "start", "-a", container], check=True)
        state = json.loads(subprocess.check_output(["docker","inspect",container]))[0]["State"]
        assert state["ExitCode"] == 0 and not state["OOMKilled"], state
        return (timestamp(state["FinishedAt"]) - timestamp(state["StartedAt"])).total_seconds()
    finally:
        subprocess.run(["docker","rm","-f",container], check=True, stdout=subprocess.DEVNULL)

for index, seed in enumerate(seeds):
    events = 20_000_000 if index == 0 else 60_000_000
    print("DATASET", seed, events, flush=True)
    subprocess.run([root/"generator/target/release/generate", "--seed",str(seed),
                    "--events",str(events),"--clicks",str(events // 4),"--threads",str(len(cpus)),
                    "--output",root/"data"],check=True)
    samples = {label: [] for label in labels}
    # Each label appears first, second and third three times across nine rounds.
    orders = [labels[i:]+labels[:i] for i in range(3)] * 3
    random.Random(seed).shuffle(orders)
    for number, order in enumerate([labels]+orders):
        for label in order:
            out, scratch = root/f"{label}-out", root/f"{label}-scratch"
            for path in [out, scratch]:
                if path.exists():
                    # Container UID 1000 owns its Parquet subdirectories.
                    subprocess.run(["sudo", "rm", "-rf", "--", str(path)], check=True)
                path.mkdir()
                path.chmod(0o777)
            seconds = elapsed(label,out,scratch)
            if number: samples[label].append(seconds)
            print("ROUND",seed,number,label,seconds,flush=True)
    for table in ["user_daily","campaign_daily"]:
        for label in ["candidate","control"]:
            a,b=[f"SELECT * FROM read_parquet('{root}/{k}-out/{table}/*.parquet')" for k in ["ranked",label]]
            for x,y in [(a,b),(b,a)]:
                assert duckdb.sql(f"SELECT count(*) FROM ({x} EXCEPT ALL {y})").fetchone()[0]==0
    for label in labels:
        median=statistics.median(samples[label])
        medians[label].append(median)
        print("MEDIAN",seed,label,median,flush=True)
    shutil.rmtree(root/"data")
for label in labels:
    mean=statistics.mean(medians[label])
    print("FINAL",label,round(mean,6),"ratio",round(mean/statistics.mean(medians["ranked"]),4),flush=True)
