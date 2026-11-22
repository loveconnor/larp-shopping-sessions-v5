use std::{fs, path::Path, time::Instant};

mod current;
mod alt16;
mod alt32;
mod alt64;
mod alt128;

fn main() {
    let mut samples: [Vec<Vec<u64>>; 7] = Default::default();
    for file in fs::read_dir(Path::new("histories")).unwrap() {
        let bytes = fs::read(file.unwrap().path()).unwrap();
        let mut input = bytes.as_slice();
        while !input.is_empty() {
            let n = u16::from_le_bytes(input[..2].try_into().unwrap()) as usize;
            let bin = [16, 32, 48, 64, 96, 128, 511].partition_point(|&max| max < n);
            let values = input[2..2 + 8*n].chunks_exact(8)
                .map(|p| u64::from_le_bytes(p.try_into().unwrap())).collect();
            samples[bin].push(values);
            input = &input[2 + 8*n..];
        }
    }
    let sorters: [(&str, fn(&mut [u64], &mut [u64])); 5] = [
        ("current",current::apply), ("alt16",alt16::apply), ("alt32",alt32::apply),
        ("alt64",alt64::apply), ("alt128",alt128::apply),
    ];
    for (bin, input) in samples.iter().enumerate() {
        if input.is_empty() { continue; }
        let mut expected = input.clone();
        for values in &mut expected { values.sort_unstable(); }
        let mut runs: [Vec<f64>; 5] = Default::default();
        let mut values = input.clone();
        let mut scratch = [0; 512];
        for round in 0..40 {
            for slot in 0..5 {
                let engine = (if round % 10 >= 5 { 4-slot } else { slot } + round) % 5;
                for (dst, src) in values.iter_mut().zip(input) { dst.copy_from_slice(src); }
                let start = Instant::now();
                for v in &mut values {
                    (sorters[engine].1)(std::hint::black_box(v), &mut scratch);
                }
                let elapsed = start.elapsed().as_nanos() as f64 / input.len() as f64;
                assert!(values == expected, "output differs in bin {bin}");
                if round >= 10 { runs[engine].push(elapsed); }
            }
        }
        for run in &mut runs { run.sort_by(f64::total_cmp); }
        let median = |v: &[f64]| (v[v.len()/2 - 1] + v[v.len()/2]) / 2.0;
        for (id, (name, _)) in sorters.iter().enumerate() {
            println!("HISTORY bin={} histories={} engine={} ns={:.1} ratio={:.4}", bin,input.len(),name,
                median(&runs[id]), median(&runs[id])/median(&runs[0]));
        }
    }
}
