import glob, os, sys, zipfile

wheels, sp = sys.argv[1], sys.argv[2]

# PyVersion tags compatible with embedded 3.13 (and forward-compat py3-any)
OK_TAGS = ("py3", "py313", "cp313", "py2.py3", "cp39", "cp310", "cp311", "cp312")

def tag_ok(fn):
    # name-1.0-<tags>.whl ; tags part = everything between 2nd and last '-'... simpler: split on '-'
    parts = fn[:-4].split('-')
    if len(parts) < 3:
        return True
    tagstr = parts[-3] if len(parts) >= 5 else parts[-1]
    # for standard wheel names: {name}-{ver}-{build?}-{pytag}-{abitag}-{plattag}
    segs = fn[:-4].split('-')
    tags = segs[-3:] if len(segs) >= 4 else segs[-2:]
    joined = '.'.join(tags)
    if 'any' in joined:
        return True
    for t in OK_TAGS:
        if t in joined:
            return True
    return False

n = 0
bad = []
for w in sorted(glob.glob(os.path.join(wheels, '*.whl'))):
    fn = os.path.basename(w)
    if not tag_ok(fn):
        bad.append(fn)
        print('   [NE TOT PYTHON] ' + fn + '  <- sobran ne dlya Python 3.13!')
        continue
    try:
        z = zipfile.ZipFile(w)
    except Exception as e:
        print('   [BAD ZIP] ' + fn + ' -> ' + str(e))
        sys.exit(2)
    names = z.namelist()
    if not any(x.endswith('__init__.py') or x.endswith('.py') for x in names):
        print('   [CORRUPT/EMPTY] ' + fn)
        sys.exit(2)
    z.extractall(sp)
    z.close()
    n += 1
    print('   + ' + fn)

print('   razpakovano arhivov: ' + str(n))
if bad:
    print('')
    print('   [!] VNIMANIE: faily ne podkhodyashie dlya Python 3.13:')
    for b in bad:
        print('       ' + b)
    print('   Kakoy u vas embedded python? Sm. papku runtime embedded.')
    print('   Dlya Python 3.13 nuzhny fily s metkami cp313 ili py3-none-any.')
    print('   Dlya Python 3.15 - eto drugie fily, skachajte so ssylok v README_WHEELS.txt')
    print('   i vybirajte variant, gde v imeni est vash nomer (napr. cp315).')
sys.exit(0 if (n >= 9 and not bad) else (3 if n < 9 else 4))
