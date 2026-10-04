"""snaplib.py - resolve virtual addresses inside an armor-watch snapshot, offline.

armor-watch.py dumps every committed RW region to <name>.bin with a <name>.json index of
[base, len, file_offset]. Given that, any virtual address in the captured process can be read
back from disk with no game running - which is the whole point here, because the game cannot be
launched over RDP.

All the armorwatch snapshots share one pid (5612, one i76.exe session), so absolute addresses
are directly comparable across them. Only the heap allocation moves, and only on a REPAIR
(the regen respawn); a pure damage event (full->hurt, prefront->frontgone) keeps the same
allocation, so the player-entity pointer is stable across those pairs.
"""
import json, os, struct, bisect

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'captures', 'armorwatch')


class Snap:
    def __init__(self, name):
        self.name = name
        meta = json.load(open(os.path.join(DIR, name + '.json')))
        self.pid = meta['pid']
        self.blob = open(os.path.join(DIR, name + '.bin'), 'rb').read()
        # sorted (base, len, file_offset) for bisect lookup
        self.index = sorted([(b, l, o) for b, l, o in meta['index']])
        self.bases = [b for b, _, _ in self.index]

    def _region(self, addr):
        i = bisect.bisect_right(self.bases, addr) - 1
        if i < 0:
            return None
        b, l, o = self.index[i]
        if b <= addr < b + l:
            return b, l, o
        return None

    def read(self, addr, n):
        r = self._region(addr)
        if not r:
            return None
        b, l, o = r
        start = o + (addr - b)
        avail = l - (addr - b)
        if avail < n:
            return None
        return self.blob[start:start + n]

    def u32(self, addr):
        d = self.read(addr, 4)
        return struct.unpack('<I', d)[0] if d else None

    def i32(self, addr):
        d = self.read(addr, 4)
        return struct.unpack('<i', d)[0] if d else None

    def f32(self, addr):
        d = self.read(addr, 4)
        return struct.unpack('<f', d)[0] if d else None

    def deref_chain(self, root, offsets):
        """root is a VA holding a pointer; follow [root] then add/deref each offset.
        offsets like ['*', 0x70] means deref then +0x70. Bare ints add; '*' derefs."""
        a = root
        for op in offsets:
            if op == '*':
                a = self.u32(a)
                if a is None:
                    return None
            else:
                a = a + op
        return a

    def player_entity(self):
        # [[[0x54A264]] + 0x70]  (Gold i76.exe static root)
        p = self.u32(0x54A264)
        if not p:
            return None
        p = self.u32(p)
        if not p:
            return None
        return self.u32(p + 0x70)

    def regions(self):
        return list(self.index)


def load(name):
    return Snap(name)
