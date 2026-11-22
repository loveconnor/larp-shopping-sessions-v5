import os
from pathlib import Path
from statistics import median
import subprocess
import sys

root = Path(os.environ["RUNNER_TEMP"])
source = root / "engine" / "native"

if sys.argv[1] == "build":
    for patch in ["wide.patch", "register-merge.patch"]:
        with (source / "platform" / patch).open() as diff:
            subprocess.run(["patch", "-p2"], cwd=source, stdin=diff, check=True)
    path = source / "src/main.rs"
    code = path.read_text()
    begin = code.index("fn session_worker(")
    i = code.index("    let mut bins = None;", begin)
    code = code[:i] + '''    let threshold: usize = std::env::var("THRESHOLD").unwrap().parse().unwrap();
    let mut lens = [[0u64; 2]; 10];
''' + code[i:]
    i = code.index("            if mine.len() < 512 {", i)
    code = code[:i] + code[i:].replace("            if mine.len() < 512 {",'''            let n = mine.len();
            let tick = (128..4096).contains(&n).then(Instant::now);
            if n < threshold {''', 1)
    i = code.index("            from = to;", i)
    code = code[:i] + '''            if let Some(started) = tick {
                let bin = [192,256,384,512,768,1024,1536,2048,3072,4096].partition_point(|&end| end <= n);
                lens[bin][0] += 1;
                lens[bin][1] += started.elapsed().as_nanos() as u64;
            }
''' + code[i:]
    i = code.index("    let wrote = sessions.writer", i)
    code = code[:i] + '''    for (band, [count, nanos]) in lens.into_iter().enumerate() {
        eprintln!("CENSUS {band} {count} {nanos}");
    }
''' + code[i:]
    path.write_text(code)
    sys.exit()

import duckdb

measured = {}
# Reverse the order every other round. The first round warms the file cache.
for round_id in range(7):
    for threshold in ([128,4096] if round_id % 2 == 0 else [4096,128]):
        output = root / f"out-{threshold}"
        output.mkdir(exist_ok=True)
        for part in output.glob("*/*.parquet"): part.unlink()
        cmd = [root/"engine/native/target/release/shopping-sessions"]
        env = os.environ | {"DATA_DIR":str(root/"data"), "OUTPUT_DIR":str(output),
                            "NCPU":str(len(os.sched_getaffinity(0))), "THRESHOLD":str(threshold)}
        res = subprocess.run(cmd, env=env, text=True, capture_output=True, check=True)
        counts = [[0,0] for _ in range(10)]
        for line in res.stderr.splitlines():
            if line.startswith("CENSUS "):
                _,band,count,nanos = line.split()
                counts[int(band)][0] += int(count)
                counts[int(band)][1] += int(nanos)
        for band,(count,nanos) in enumerate(counts):
            if count and round_id:
                measured.setdefault((band,threshold),[]).append(nanos/count)
        assert sum(count for count,_ in counts)>0
for table in ["user_daily","campaign_daily"]:
    a,b = [f"SELECT * FROM read_parquet('{root}/out-{t}/{table}/*.parquet')" for t in [128,4096]]
    for left,right in [(a,b),(b,a)]:
        assert duckdb.sql(f"SELECT count(*) FROM ({left} EXCEPT ALL {right})").fetchone()[0] == 0
for band in range(10):
    if (band,128) not in measured: continue
    binned = median(measured[band,128])
    sorted_time = median(measured[band,4096])
    print(f"CROSSOVER band={band} shoppers={counts[band][0]} sort_ns={sorted_time:.1f} bin_ns={binned:.1f} ratio={sorted_time/binned:.4f}")
