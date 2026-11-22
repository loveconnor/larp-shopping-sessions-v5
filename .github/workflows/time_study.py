from pathlib import Path
import os, subprocess as sp, statistics, random, time, shutil, duckdb
root=Path(os.environ['RUNNER_TEMP'])
names=sorted(p.name for p in (root/'engines').glob('*-*'))
rng=random.Random(int(os.environ['SEED']))
for d in ['output','scratch']:
    (root/d).mkdir()
    (root/d).chmod(0o777)
cid=sp.check_output(['docker','run','-d','--memory','12g','--memory-swap','12g','--read-only','--network','none','--cap-drop','ALL','--user','1000:1000','--tmpfs','/tmp:rw,size=64m','-e','DATA_DIR=/data','-e','OUTPUT_DIR=/output','-e','NCPU=8','-e','LD_PRELOAD=libjemalloc.so.2','-e','MALLOC_CONF=narenas:2,background_thread:false,dirty_decay_ms:-1,muzzy_decay_ms:-1,thp:always,metadata_thp:auto','-v',f'{root}/test:/data:ro','-v',f'{root}/output:/output','-v',f'{root}/engines:/engines:ro','profile-runtime','sleep','2400'],text=True).strip()
samples={n:[] for n in names}
def run(n):
    sp.run(['docker','exec',cid,'rm','-rf','/output/campaign_daily','/output/user_daily'],check=True)
    start=time.perf_counter()
    sp.run(['docker','exec',cid,'/engines/'+n],check=True,capture_output=True)
    return time.perf_counter()-start
try:
    run('base-original')
    shutil.copytree(root/'output',root/'ref')
    for rnd in range(8):
        rng.shuffle(names)
        for n in names:
            elapsed=run(n)
            if rnd: samples[n].append(elapsed)
            else:
                with duckdb.connect() as con:
                    for t in ['user_daily','campaign_daily']:
                        x,y=[f"SELECT * FROM read_parquet('{root}/{d}/{t}/*.parquet')" for d in ['output','ref']]
                        for a,b in ((x,y),(y,x)):
                            assert con.sql(f'SELECT count(*) FROM ({a} EXCEPT ALL {b})').fetchone()[0]==0
    reference=samples['base-original']
    for n in sorted(names):
        m=statistics.median(samples[n])
        print('MATCHED',n,'seconds',round(m,6),'vs-original',round(m/statistics.median(samples['base-original']),4),'vs-matched',round(m/statistics.median(samples['base-matched']),4),'paired',round(statistics.median(x/y for x,y in zip(samples[n],reference)),4),'wins',sum(x<y for x,y in zip(samples[n],reference)),flush=True)
finally:
    sp.run(['docker','rm','-f',cid],check=True)
