"""Gated install / uninstall of the HD sound pack into a LAB game folder's ADDON\\ (docs/SOUND-HD-PACK.md 3.5).

Rules, all enforced here, all unit-tested against a temporary fake game folder (tests/test_soundhd.py):
  * the target must BE a folder matching <lab>\\game* (after resolving links), must
    contain I76.ZFS, and must not be under a denied root (the daily driver, the pristine GOG copy);
  * default is a dry run; --apply writes;
  * preflight refuses the whole install if any target name already exists in ADDON\\ with an md5 that is neither
    this pack's file nor a file a previous soundhd install recorded (the sandbox ADDON carries the owner's mods);
  * every written file is read back and its md5 compared (a mismatch rolls back this run's writes);
  * ADDON\\.sound-hd-installed.json records what was installed; uninstall deletes only files whose md5 still
    matches that record.
The CLI never exposes `allowed_roots`; only the tests pass their own.
"""
import fnmatch, hashlib, json, os, time

ALLOWED_ROOTS = [(__import__("os").path.expanduser("~") + r"\i76-uncap-lab\game*")]
DENIED_ROOTS = [(__import__("os").path.expanduser("~") + r"\Games"), (__import__("os").path.expanduser("~") + r"\i76-map\sandbox-gog")]
RECORD = ".sound-hd-installed.json"


class InstallRefused(Exception):
    pass


def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm(p):
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def check_target(game, allowed_roots=None, denied_roots=None):
    """Return the resolved game folder or raise InstallRefused."""
    allowed_roots = ALLOWED_ROOTS if allowed_roots is None else allowed_roots
    denied_roots = DENIED_ROOTS if denied_roots is None else denied_roots
    real = _norm(game)
    for d in denied_roots:
        dn = _norm(d)
        if real == dn or real.startswith(dn + os.sep):
            raise InstallRefused("refused: %s is under a denied root (%s)" % (game, d))
    ok = False
    for pat in allowed_roots:
        parent, glob = os.path.split(pat)
        if os.path.dirname(real) == _norm(parent) and fnmatch.fnmatch(os.path.basename(real), os.path.normcase(glob)):
            ok = True
    if not ok:
        raise InstallRefused("refused: %s is not a folder matching %s" % (game, " or ".join(allowed_roots)))
    if not os.path.isdir(real):
        raise InstallRefused("refused: %s does not exist" % game)
    if not any(n.lower() == "i76.zfs" for n in os.listdir(real)):
        raise InstallRefused("refused: %s has no I76.ZFS (not a game folder)" % game)
    return real


def _addon_dir(real, create):
    for n in os.listdir(real):
        if n.lower() == "addon" and os.path.isdir(os.path.join(real, n)):
            return os.path.join(real, n)
    if create:
        p = os.path.join(real, "ADDON")
        os.makedirs(p)
        return p
    return None


def _listing(addon):
    return {n.lower(): n for n in os.listdir(addon)} if addon and os.path.isdir(addon) else {}


def _read_record(addon):
    p = os.path.join(addon, RECORD) if addon else None
    if p and os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def load_pack(pack):
    """(manifest, {addon_name: (src_path, md5)}) with every pack file re-hashed against the manifest."""
    with open(os.path.join(pack, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    files = {}
    for s in man["sounds"]:
        if not s.get("replacement"):
            continue
        name = s["replacement"]["file"]
        src = os.path.join(pack, "addon", name)
        got = md5_file(src)
        if got != s["replacement"]["md5"]:
            raise InstallRefused("pack file %s md5 %s != manifest %s (rebuild the manifest)" % (name, got, s["replacement"]["md5"]))
        files[name] = (src, got)
    return man, files


def install(pack, game, apply=False, allowed_roots=None, denied_roots=None, log=print):
    real = check_target(game, allowed_roots, denied_roots)
    man, files = load_pack(pack)
    addon = _addon_dir(real, create=False)
    have = _listing(addon)
    rec = _read_record(addon) or {"files": {}}
    ours_before = {k.lower(): v for k, v in rec.get("files", {}).items()}
    plan, conflicts = [], []
    for name, (src, md5) in sorted(files.items()):
        existing = have.get(name.lower())
        if existing:
            cur = md5_file(os.path.join(addon, existing))
            if cur == md5:
                plan.append((name, src, md5, "same"))
            elif ours_before.get(name.lower()) == cur:
                plan.append((name, src, md5, "update"))
            else:
                conflicts.append("%s (md5 %s is not in the pack manifest or the install record)" % (existing, cur))
        else:
            plan.append((name, src, md5, "new"))
    if conflicts:
        raise InstallRefused("refused: ADDON files not owned by soundhd would be overwritten:\n  " + "\n  ".join(conflicts))
    log("install %s -> %s (%s)" % (man.get("pack_version"), addon or os.path.join(real, "ADDON"), "APPLY" if apply else "dry run"))
    for name, _, md5, what in plan:
        log("  %-6s %s %s" % (what, md5, name))
    if not apply:
        return dict(dry_run=True, plan=[(n, w) for n, _, _, w in plan])
    addon = _addon_dir(real, create=True)
    written = []
    try:
        for name, src, md5, what in plan:
            dst = os.path.join(addon, have.get(name.lower(), name))
            if what != "same":
                tmp = dst + ".soundhd-tmp"
                with open(src, "rb") as fi, open(tmp, "wb") as fo:
                    fo.write(fi.read())
                os.replace(tmp, dst)
                written.append(dst)
            back = md5_file(dst)
            if back != md5:
                raise InstallRefused("read-back md5 mismatch on %s: %s != %s" % (dst, back, md5))
    except Exception:
        for p in written:
            try:
                os.remove(p)
            except OSError:
                pass
        raise
    record = dict(pack_version=man.get("pack_version"), installed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  files={os.path.basename(os.path.join(addon, have.get(n.lower(), n))): m for n, _, m, _ in plan})
    with open(os.path.join(addon, RECORD), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
    log("installed %d files (%d written, read back OK)" % (len(plan), len(written)))
    return dict(dry_run=False, installed=len(plan), written=len(written))


def uninstall(game, apply=False, allowed_roots=None, denied_roots=None, log=print):
    real = check_target(game, allowed_roots, denied_roots)
    addon = _addon_dir(real, create=False)
    rec = _read_record(addon)
    if not rec:
        raise InstallRefused("nothing to uninstall: no %s in %s" % (RECORD, addon or real))
    have = _listing(addon)
    delete, kept, missing = [], {}, []
    for name, md5 in sorted(rec["files"].items()):
        existing = have.get(name.lower())
        if not existing:
            missing.append(name)
            continue
        p = os.path.join(addon, existing)
        if md5_file(p) == md5:
            delete.append(p)
        else:
            kept[name] = md5
    log("uninstall from %s (%s): delete %d, kept (changed since install) %d, already gone %d" % (
        addon, "APPLY" if apply else "dry run", len(delete), len(kept), len(missing)))
    for k in kept:
        log("  KEPT (md5 differs from the record): " + k)
    if not apply:
        return dict(dry_run=True, delete=[os.path.basename(p) for p in delete], kept=sorted(kept), missing=missing)
    for p in delete:
        os.remove(p)
    rp = os.path.join(addon, RECORD)
    if kept:
        rec["files"] = kept
        with open(rp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True)
    else:
        os.remove(rp)
    return dict(dry_run=False, deleted=len(delete), kept=sorted(kept), missing=missing)
