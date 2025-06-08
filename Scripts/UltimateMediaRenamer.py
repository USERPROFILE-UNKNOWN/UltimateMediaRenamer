import os
import sys
import re
import shutil
import json
import sqlite3
import argparse
import hashlib
import subprocess
import traceback
from datetime import datetime
from collections import namedtuple, defaultdict
from pathlib import Path

# =============== SHARED CONFIGURATION =============== #
BASE_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(BASE_DIR, "Database", "UltimateMediaRenamer.db")
CONFIG_PATH   = os.path.join(os.path.dirname(__file__), 'platforms.json')
TOOLS_DIR     = os.path.join(BASE_DIR, "Tools")
Platform      = namedtuple('Platform', ['name', 'folder', 'patterns', 'pass_num'])

# ================ DATABASE INITIALIZATION ================ #
def initialize_database():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS operations_log (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path           TEXT,
                new_path                TEXT,
                operation               TEXT,
                platform_detected       TEXT,
                timestamp               TEXT,
                true_original_path      TEXT,
                move_chain_id           TEXT,
                original_name           TEXT,
                new_name                TEXT,
                earliest_metadata_date  TEXT,
                exif_date               TEXT,
                xmp_date                TEXT,
                ffprobe_date            TEXT,
                mediainfo_date          TEXT,
                fallback_date           TEXT,
                file_hash               TEXT
            )
        ''')
        conn.commit()

# =============== ONE-TIME ORIGINAL LOGGING =============== #
def ensure_original_logged(filepath):
    """Record original_name & true_original_path once, never overwrite."""
    filepath = os.path.abspath(filepath)
    initialize_database()
    with sqlite3.connect(DATABASE_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT original_name, true_original_path
              FROM operations_log
             WHERE original_path=? OR new_path=?
             ORDER BY id ASC LIMIT 1
        ''', (filepath, filepath))
        row = c.fetchone()
        if not row:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute('''
                INSERT INTO operations_log (
                    original_path, new_path, operation,
                    timestamp, true_original_path, original_name
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                filepath, filepath, "first_seen",
                now, filepath, os.path.basename(filepath)
            ))
            conn.commit()
        else:
            orig_name, true_orig = row
            updates = []
            if not orig_name:
                updates.append(("original_name", os.path.basename(filepath)))
            if not true_orig:
                updates.append(("true_original_path", filepath))
            for col, val in updates:
                c.execute(f'''
                    UPDATE operations_log
                       SET {col}=?
                     WHERE original_path=? OR new_path=?
                ''', (val, filepath, filepath))
            if updates:
                conn.commit()

# =============== HELPERS =============== #
def find_closest_organized_root(start_path):
    p = Path(start_path).resolve()
    for parent in p.parents:
        if parent.name.lower() == "organized":
            return str(parent)
    return None

def compute_file_hash(path, block_size=65536):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            buf = f.read(block_size)
            while buf:
                h.update(buf)
                buf = f.read(block_size)
        return h.hexdigest()
    except:
        return None

def run_command(cmd):
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return res.stdout.strip()
    except:
        return ""

def extract_all_metadata_dates(filepath):
    dates = {}
    exif = os.path.join(TOOLS_DIR, "exiftool.exe")
    if os.path.exists(exif):
        keys = [
            "DateTimeOriginal", "CreateDate", "ModifyDate",
            "XMP:CreateDate", "XMP:DateCreated", "XMP:ModifyDate",
            "FileCreateDate", "FileModifyDate",
            "QuickTime:CreateDate", "QuickTime:ModifyDate",
            "ID3:Year", "ID3:Date"
        ]
        out = run_command([exif, "-s3"] + [f"-{k}" for k in keys] + [filepath]).splitlines()
        for k, v in zip(keys, out + [""]*len(keys)):
            dates[k.lower()] = v
    ff = os.path.join(TOOLS_DIR, "ffprobe.exe")
    if os.path.exists(ff):
        dates["ffprobe_date"] = run_command([
            ff, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format_tags=creation_time",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath
        ])
    mi = os.path.join(TOOLS_DIR, "MediaInfo.exe")
    if os.path.exists(mi):
        dates["mediainfo_date"] = run_command([mi, "--Inform=General;%Encoded_Date%", filepath])
    dates["filesystem_mtime"] = datetime.utcfromtimestamp(os.path.getmtime(filepath))\
                                .strftime("%Y-%m-%d %H:%M:%S")
    return dates

def parse_date_string(s):
    if not s: return None
    s = s.split('.')[0].replace('Z','')
    fmts = ["%Y:%m:%d %H:%M:%S","%Y-%m-%d %H:%M:%S","%Y%m%d_%H%M%S","%Y%m%d","%Y-%m-%d","%Y"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if 1900 <= dt.year <= 2100:
                return dt
        except:
            continue
    return None

def find_earliest_date(fp):
    dates = extract_all_metadata_dates(fp)
    valid = []
    for k, v in dates.items():
        if k=="id3:year" and v.isdigit() and len(v)==4:
            y = int(v)
            if 1900 <= y <= 2100:
                valid.append(datetime(y,1,1))
        else:
            dt = parse_date_string(v)
            if dt:
                valid.append(dt)
    return min(valid) if valid else None

def is_already_properly_named(fp):
    name = os.path.splitext(os.path.basename(fp))[0]
    if not re.match(r'^\d{8}_\d{6}(_\d{2})?$', name):
        return False
    earliest = find_earliest_date(fp)
    return earliest and name.startswith(earliest.strftime("%Y%m%d_%H%M%S"))

def generate_new_filename(dt, ext):
    return f"{dt.strftime('%Y%m%d_%H%M%S')}{ext}"

# =============== RENAME FUNCTIONS =============== #
def create_rename_plan(filepath):
    plan = {}
    if os.path.isdir(filepath):
        print(f"Skipping directory: {filepath}")
        return plan
    if is_already_properly_named(filepath):
        print(f"Already correct: {os.path.basename(filepath)}")
        return plan
    earliest = find_earliest_date(filepath)
    if not earliest:
        print(f"No valid date for: {os.path.basename(filepath)}")
        return plan
    ext = os.path.splitext(filepath)[1].lower()
    newn = generate_new_filename(earliest, ext)
    plan[os.path.abspath(filepath)] = (newn, earliest)
    return plan

def resolve_conflicts(rename_plan):
    dir_groups = defaultdict(list)
    for orig, (newn, _) in rename_plan.items():
        dir_groups[os.path.dirname(orig)].append((orig, newn))
    for d, items in dir_groups.items():
        counts = defaultdict(int)
        exists = set(os.listdir(d))
        for _, newn in items:
            counts[newn] += 1
        used = {}
        for orig, newn in items:
            base, ext = os.path.splitext(newn)
            final = newn
            cnt = 1
            while (counts[newn] > 1 and used.get(newn,0) > 0) or final in exists:
                cnt += 1
                final = f"{base} ({cnt}){ext}"
            used[newn] = used.get(newn,0) + 1
            rename_plan[orig] = (final, rename_plan[orig][1])
            exists.add(final)
    return rename_plan

def execute_rename(rename_plan):
    for orig, (newn, earliest) in rename_plan.items():
        newp = os.path.join(os.path.dirname(orig), newn)
        if os.path.abspath(orig) == os.path.abspath(newp):
            print(f"No rename needed: {os.path.basename(orig)}")
            continue
        try:
            os.rename(orig, newp)
            h   = compute_file_hash(newp)
            md  = extract_all_metadata_dates(newp)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(DATABASE_PATH) as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO operations_log (
                        original_path, new_path, operation,
                        timestamp, original_name, new_name,
                        earliest_metadata_date, exif_date, xmp_date,
                        ffprobe_date, mediainfo_date, fallback_date,
                        file_hash, true_original_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    orig, newp, "rename",
                    now, os.path.basename(orig), newn,
                    earliest.strftime("%Y-%m-%d %H:%M:%S"),
                    md.get("exif_datetimeoriginal",""),
                    md.get("xmp:createdate",""),
                    md.get("ffprobe_date",""),
                    md.get("mediainfo_date",""),
                    md.get("filesystem_mtime",""),
                    h,
                    orig
                ))
                conn.commit()
            print(f"Renamed: {os.path.basename(orig)} → {newn}")
        except Exception as e:
            print(f"Error renaming {orig}: {e}")
            traceback.print_exc()

def rename_file(filepath):
    ensure_original_logged(filepath)
    plan = create_rename_plan(filepath)
    if plan:
        plan = resolve_conflicts(plan)
        execute_rename(plan)

def process_dir_for_rename(directory, recursive=False):
    base = Path(directory)
    files = [f for f in (base.rglob('*') if recursive else base.iterdir()) if f.is_file()]
    # PRE-LOG
    for f in files:
        ensure_original_logged(str(f))
    # PROCESS
    for f in files:
        rename_file(str(f))

# =============== UNDO & RESTORE FUNCTIONS =============== #
def undo_last_rename(target):
    ensure_original_logged(target)
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT original_path,new_path,operation
                  FROM operations_log
                 WHERE (original_path=? OR new_path=?)
                   AND operation IN ('rename','categorize','duplicate_clean')
                 ORDER BY id DESC LIMIT 1
            ''', (target, target))
            row = c.fetchone()
            if not row:
                print(f"No record for: {target}")
                return
            orig, newp, op = row
            if os.path.exists(newp):
                if op == 'rename':
                    os.rename(newp, orig)
                else:
                    shutil.move(newp, orig)
                c.execute('''
                    INSERT INTO operations_log
                        (original_path,new_path,operation)
                      VALUES (?,?,?)
                ''', (newp, orig, "undo"))
                conn.commit()
                print(f"Undo: {os.path.basename(newp)} → {os.path.basename(orig)}")
    except Exception as e:
        print(f"Undo failed: {e}")

def process_dir_undo(directory, recursive=False):
    base = Path(directory)
    files = [f for f in (base.rglob('*') if recursive else base.iterdir()) if f.is_file()]
    # PRE-LOG
    for f in files:
        ensure_original_logged(str(f))
    # UNDO
    for f in files:
        undo_last_rename(str(f))

def restore_original(target, full_history=False):
    ensure_original_logged(target)
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            if full_history:
                query = '''
                    SELECT original_path,new_path,operation
                      FROM operations_log
                     WHERE original_path=? OR new_path=?
                     ORDER BY id ASC
                '''
            else:
                query = '''
                    SELECT original_path,new_path,operation
                      FROM operations_log
                     WHERE (original_path=? OR new_path=?)
                       AND operation IN ('rename','categorize','duplicate_clean')
                     ORDER BY id ASC
                '''
            c.execute(query, (target,target))
            hist = c.fetchall()
            if not hist:
                print(f"No history for: {target}")
                return
            first_orig = hist[0][0]
            curr = target
            for orig, newp, op in hist:
                if orig == curr and op in ('rename','categorize','duplicate_clean'):
                    curr = newp
                elif newp == curr and op in ('undo','restore'):
                    curr = orig
            if os.path.exists(curr):
                if os.path.isfile(curr):
                    os.rename(curr, first_orig)
                else:
                    shutil.move(curr, first_orig)
                # log restore with true_original_path
                c.execute('''
                    INSERT INTO operations_log
                      (original_path,new_path,operation,true_original_path)
                    VALUES (?,?,?,?)
                ''', (curr, first_orig, "restore", first_orig))
                conn.commit()
                print(f"Restored: {os.path.basename(curr)} → {os.path.basename(first_orig)}")
    except Exception as e:
        print(f"Restore failed: {e}")

def process_dir_restore(directory, recursive=False):
    base = Path(directory)
    files = [f for f in (base.rglob('*') if recursive else base.iterdir()) if f.is_file()]
    # PRE-LOG
    for f in files:
        ensure_original_logged(str(f))
    # RESTORE
    for f in files:
        restore_original(str(f), full_history=True)

# =============== ORGANIZE FUNCTIONS =============== #
def get_unique_filename(dest):
    dirn, fn = os.path.split(dest)
    base, ext = os.path.splitext(fn)
    m = re.match(r'^(.*) \((\d+)\)$', base)
    name = m.group(1) if m else base
    cnt  = int(m.group(2)) if m else 1
    while True:
        cnt += 1
        new = f"{name} ({cnt}){ext}"
        if not os.path.exists(os.path.join(dirn,new)):
            return os.path.join(dirn,new)

def organize_run(directory, recursive=False):
    base = Path(directory)

    if base.is_file():
        # Handle single-file organize
        files = [str(base)]
        org_root = find_closest_organized_root(base) or str(base.parent)
    else:
        if not base.exists():
            print(f"Dir not found: {directory}")
            return
        files = [str(f) for f in (base.rglob('*') if recursive else base.iterdir()) if f.is_file()]
        org_root = find_closest_organized_root(directory) or os.path.join(directory, "Organized")

    # PRE-LOG
    for f in files:
        ensure_original_logged(f)

    os.makedirs(org_root, exist_ok=True)

    with open(CONFIG_PATH, 'r', encoding='utf-8') as cf:
        cfg = json.load(cf)['platforms']
    platforms = [
        Platform(p['name'], p['folder'],
                 [re.compile(rx) for rx in p['filename_patterns']],
                 p['pass']) for p in cfg
    ]

    for f in files:
        fn = os.path.basename(f)
        moved = False
        for plat in platforms:
            if any(rx.match(fn) for rx in plat.patterns):
                dest_dir = os.path.join(org_root, plat.folder)
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, fn)

                # ✅ Skip moving if already correctly organized
                if os.path.abspath(f) == os.path.abspath(dest):
                    print(f"Already organized: {fn}")
                    moved = True
                    break

                # Handle filename collisions
                if os.path.exists(dest):
                    dest = get_unique_filename(dest)

                shutil.move(f, dest)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with sqlite3.connect(DATABASE_PATH) as conn:
                    c = conn.cursor()
                    c.execute('''
                        SELECT true_original_path
                          FROM operations_log
                         WHERE new_path=?
                         ORDER BY id ASC LIMIT 1
                    ''', (f,))
                    row = c.fetchone()
                    true_orig = row[0] if row else f
                    c.execute('''
                        INSERT INTO operations_log (
                            original_path,new_path,operation,
                            timestamp,platform_detected,true_original_path
                        ) VALUES (?,?,?,?,?,?)
                    ''', (f, dest, "categorize", now, plat.name, true_orig))
                    conn.commit()
                print(f"Moved: {fn} → {dest} [{plat.name}]")
                moved = True
                break
        if not moved:
            print(f"No match: {fn}")

def restore_locations(directory, recursive=False):
    base = Path(directory)

    if base.is_file():
        files = [str(base)]
    elif base.is_dir():
        files = [str(f) for f in (base.rglob('*') if recursive else base.iterdir()) if f.is_file()]
    else:
        print(f"Path not found: {directory}")
        return

    # PRE-LOG
    for f in files:
        ensure_original_logged(f)

    for f in files:
        with sqlite3.connect(DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('''
                SELECT true_original_path
                  FROM operations_log
                 WHERE new_path=?
                 ORDER BY id ASC LIMIT 1
            ''', (f,))
            row = c.fetchone()

        if row:
            orig_loc = row[0]
            if os.path.abspath(f) != os.path.abspath(orig_loc):
                os.makedirs(os.path.dirname(orig_loc), exist_ok=True)
                shutil.move(f, orig_loc)
                print(f"Restored loc: {os.path.basename(f)} → {orig_loc}")
        else:
            print(f"No original path found for: {f}")

# =============== DUPLICATE CLEANER =============== #
def compute_hash(fp, chunk_size=8192):
    sha1 = hashlib.sha1()
    with open(fp,'rb') as f:
        while buf := f.read(chunk_size):
            sha1.update(buf)
    return sha1.hexdigest()

def find_duplicates(directory):
    hashes = {}
    for entry in os.scandir(directory):
        if entry.is_file():
            h = compute_hash(entry.path)
            hashes.setdefault(h, []).append(Path(entry.path))
    return {h:ps for h,ps in hashes.items() if len(ps) > 1}

def select_best(paths):
    stats = []
    for p in paths:
        size = p.stat().st_size
        has_ctr = bool(re.search(r' \(\d+\)\.', p.name))
        stats.append((p, size, has_ctr))
    stats.sort(key=lambda x: (-x[1], x[2]))
    keep = stats[0][0]
    to_move = [p for p,_,_ in stats[1:]]
    return keep, to_move

def log_duplicate_move(orig, newp, file_hash):
    with sqlite3.connect(DATABASE_PATH) as conn:
        c = conn.cursor()
        ts = datetime.utcnow().isoformat() + 'Z'
        chain = hashlib.md5(f"{orig}{ts}".encode()).hexdigest()
        c.execute('''
            INSERT INTO operations_log (
                original_path,new_path,operation,
                platform_detected,timestamp,true_original_path,
                move_chain_id,original_name,new_name,file_hash
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            str(orig), str(newp), 'duplicate_clean',
            'Duplicates', ts, str(orig), chain,
            orig.name, newp.name, file_hash
        ))
        conn.commit()

def move_duplicates(dupes, target_dir):
    target_dir = Path(target_dir)
    target_dir.mkdir(exist_ok=True)
    # PRE-LOG
    for paths in dupes.values():
        for p in paths:
            ensure_original_logged(str(p))
    for paths in dupes.values():
        keep, to_mv = select_best(paths)
        for p in to_mv:
            dest = target_dir / p.name
            cnt  = 1
            while dest.exists():
                stem, suf = dest.stem, dest.suffix
                dest = target_dir / f"{stem}_(dup{cnt}){suf}"
                cnt += 1
            h = compute_hash(str(p))
            shutil.move(str(p), str(dest))
            log_duplicate_move(p, dest, h)
            print(f"Moved dup: {p.name} → {dest.name}")

# =============== MAIN HANDLER =============== #
def main():
    parser = argparse.ArgumentParser(prog="UltimateMediaRenamer")
    sub = parser.add_subparsers(dest="mode", required=True)

    # rename
    r = sub.add_parser('rename')
    r.add_argument('action', choices=[
        'single',
        'batch',
        'undo',
        'undo-batch',
        'restore-original',
        'restore-original-batch'
    ])
    r.add_argument('targets', nargs='+')
    r.add_argument('--recursive', '-r', action='store_true')

    # organize
    o = sub.add_parser('organize')
    o.add_argument('action', choices=['run', 'restore-dir'])
    o.add_argument('directory')
    o.add_argument('--recursive', '-r', action='store_true')

    # clean-duplicates
    d = sub.add_parser('clean-duplicates')
    d.add_argument('directory')
    d.add_argument('--recursive', '-r', action='store_true')

    args = parser.parse_args()

    if args.mode == 'rename':
        if args.action == 'single':
            for t in args.targets:
                rename_file(t)
        elif args.action == 'batch':
            for t in args.targets:
                process_dir_for_rename(t, recursive=args.recursive)
        elif args.action == 'undo':
            for t in args.targets:
                undo_last_rename(t)
        elif args.action == 'undo-batch':
            for t in args.targets:
                process_dir_undo(t, recursive=args.recursive)
        elif args.action == 'restore-original':
            for t in args.targets:
                restore_original(t, full_history=True)
        elif args.action == 'restore-original-batch':
            for t in args.targets:
                process_dir_restore(t, recursive=args.recursive)

    elif args.mode == 'organize':
        if args.action == 'run':
            organize_run(args.directory, recursive=args.recursive)
        else:  # restore-dir
            restore_locations(args.directory, recursive=args.recursive)

    elif args.mode == 'clean-duplicates':
        doubles = os.path.join(args.directory, 'Doubles')
        os.makedirs(doubles, exist_ok=True)
        dupes = find_duplicates(args.directory)
        move_duplicates(dupes, doubles)

if __name__ == "__main__":
    main()
