from pathlib import Path
import subprocess, os
root=Path(os.environ['RUNNER_TEMP']); src=root/'candidate'; src.mkdir()
labels={'current':'f5364f4a92df4eec0d5f5556deadd3c2dcb64f30','merge64':'09a579006f99579417b9eb45d65c109b8ca91843','merge128':'6670741f51adb9885c2a0371d859b19cf4db9087','registers':'b6feb739d5677836969c5eed5f1139e49822feaa'}
with subprocess.Popen(['git','archive',labels['current'],'native'],stdout=subprocess.PIPE) as arc:
    subprocess.run(['tar','xf','-','-C',src],stdin=arc.stdout,check=True)
p=src/'native/src/main.rs';s=p.read_text()
i=s.index('    let mut bins = None;',s.index('fn session_worker('))
s=s[:i]+'''    use std::io::Write;
    let mut capture = std::io::BufWriter::new(std::fs::File::create(
        std::path::Path::new(&std::env::var("HISTORIES").unwrap()).join(thread.to_string()))?);
    let mut captured = [0; 7];
'''+s[i:]
i=s.index('            if mine.len() < 512 {',i)
s=s[:i]+'''            if (5..512).contains(&mine.len()) {
                let band = [16,32,48,64,96,128,511].partition_point(|&max| max < mine.len());
                if captured[band] < 512 {
                    captured[band] += 1;
                    capture.write_all(&(mine.len() as u16).to_le_bytes())?;
                    for v in mine.iter() { capture.write_all(&v.to_le_bytes())?; }
                }
            }
'''+s[i:];p.write_text(s)
for label,sha in labels.items():
    s=subprocess.check_output(['git','show',sha+':native/src/main.rs'],text=True)
    first=min(i for name in ['unsafe fn sort_short_times(', 'unsafe fn sorted_registers('] if (i:=s.find(name))!=-1)
    a=s.rindex('#[cfg(',0,first);b=s.index('fn session_worker(',a)
    (root/(label+'.rs')).write_text(s[a:b]+'\npub fn apply(v:&mut [u64], scratch:&mut [u64]) {sort_medium_times(v,scratch,12)}\n')
