import sys
from pathlib import Path
p=Path('src/main.rs'); code=p.read_text(); tag=sys.argv[1]
line=next(x for x in code.splitlines() if 'asm!("prefetchw' in x)
rewrite=line
if tag=='off':
    rewrite='            {}'
elif tag.startswith('line'):
    rewrite='            if (at as usize & 63) < size_of::<T>() {\n    '+line.replace('+ 64','+ '+tag[4:])+'\n            }'
elif tag in ('parsed128','event128'):
    name='Parsed' if tag=='parsed128' else 'Event'
    rewrite=line.replace('+ 64','+ {dist}').replace('p = in(reg)',f'dist = const (if size_of::<T>() == size_of::<{name}>() {{128}} else {{64}}), p = in(reg)')
elif tag.startswith('p'):
    rewrite=line.replace('+ 64','+ '+str(int(tag[1:])))
else:
    assert tag=='reference'
p.write_text(code.replace(line,rewrite))
