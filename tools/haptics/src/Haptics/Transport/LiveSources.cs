using System;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Net;
using System.Net.Sockets;

namespace Haptics.Transport
{
    /// <summary>
    /// Reader for Local\I76Telemetry (i76tel_shm_t). Opens the mapping READ-ONLY and never creates it, so a host
    /// started before the game does not leave a zero-filled block behind for the proxy to adopt (memory note:
    /// stale shared-memory trap). Seqlock: read seq, copy, re-read seq; accept if equal, even and non-zero.
    /// Liveness is an ADVANCING seq (<see cref="StaleSeconds"/>), never the magic alone.
    /// The returned bytes are datagram-shaped (frame + the ring entries new since the last call), like i76tel.py --shm.
    /// </summary>
    public sealed class ShmReader : IDisposable
    {
        MemoryMappedFile _mmf; MemoryMappedViewAccessor _view;
        public readonly string Name;
        uint _lastSeq; uint _lastEv; bool _primed;
        DateTime _lastAdvance = DateTime.UtcNow;
        public long Torn, Reads;

        public ShmReader(string name = @"Local\I76Telemetry") { Name = name; }

        public bool TryOpen()
        {
            if (_view != null) return true;
            try
            {
                _mmf = MemoryMappedFile.OpenExisting(Name, MemoryMappedFileRights.Read);
                _view = _mmf.CreateViewAccessor(0, 0, MemoryMappedFileAccess.Read);
                return true;
            }
            catch (FileNotFoundException) { return false; }
            catch (IOException) { return false; }
        }

        public double StaleSeconds => (DateTime.UtcNow - _lastAdvance).TotalSeconds;

        /// <summary>A new consistent frame as datagram bytes, or null (none yet, being written, unchanged, torn).</summary>
        public byte[] Poll()
        {
            if (!TryOpen()) return null;
            Reads++;
            uint seq0 = _view.ReadUInt32(0);
            if (seq0 == 0 || (seq0 & 1) != 0 || seq0 == _lastSeq) return null;
            uint total = _view.ReadUInt32(4);
            long cap = _view.Capacity;
            if (total < 8 + 16 || total > cap) total = (uint)cap;
            var buf = new byte[total];
            _view.ReadArray(0, buf, 0, buf.Length);
            uint seq1 = _view.ReadUInt32(0);
            if (seq1 != seq0) { Torn++; return null; }
            _lastSeq = seq0; _lastAdvance = DateTime.UtcNow;
            return Splice(buf, ref _lastEv, ref _primed);
        }

        /// <summary>
        /// shm block -> datagram: frame bytes followed by ring entries [lastEv+1 .. event_seq], event_count patched.
        /// Static so it can be tested on a synthetic block without a mapping.
        /// </summary>
        public static byte[] Splice(byte[] shm, ref uint lastEv, ref bool primed)
        {
            int frameOff = 8;
            int version = BitConverter.ToUInt16(shm, frameOff + 4);
            int fsize = BitConverter.ToUInt16(shm, frameOff + 6);
            if (fsize <= 16 || frameOff + fsize > shm.Length) return null;
            var codec = new TelCodec(I76TelLayout.TryLoadLive());
            var L = codec.LayoutFor(version) ?? I76TelLayout.V2;
            int ring = L.Ring > 0 ? L.Ring : 64;
            int ringOff = frameOff + fsize;
            int esz = (shm.Length - ringOff) / ring;
            if (esz != 36 && esz != 56) esz = L.Event.Size;
            var frame = new byte[fsize];
            Array.Copy(shm, frameOff, frame, 0, fsize);
            int seqOff = I76TelLayout.V2.Frame["event_seq"].Offset;    // 620 in v2 and v3: later versions append after event_count
            int cntOff = seqOff + 4;
            uint evSeq = BitConverter.ToUInt32(frame, seqOff);
            if (!primed) { lastEv = evSeq; primed = true; }       // join mid-session: do not replay the whole ring
            int n = evSeq >= lastEv ? (int)Math.Min(evSeq - lastEv, (uint)ring) : 0;
            var outb = new byte[fsize + n * esz];
            Array.Copy(frame, outb, fsize);
            for (int k = 0; k < n; k++)
            {
                uint s = evSeq - (uint)n + 1 + (uint)k;
                int o = ringOff + (int)(s % (uint)ring) * esz;
                if (o + esz <= shm.Length) Array.Copy(shm, o, outb, fsize + k * esz, esz);
            }
            BitConverter.GetBytes((uint)n).CopyTo(outb, cntOff);
            lastEv = evSeq;
            return outb;
        }

        public void Dispose() { _view?.Dispose(); _mmf?.Dispose(); }
    }

    /// <summary>UDP listener on 127.0.0.1:port (default 7676). Loopback only.</summary>
    public sealed class UdpListener : IDisposable
    {
        readonly UdpClient _u;
        public readonly int Port;
        public UdpListener(int port = 7676)
        {
            _u = new UdpClient(new IPEndPoint(IPAddress.Loopback, port));
            Port = ((IPEndPoint)_u.Client.LocalEndPoint).Port;
            _u.Client.ReceiveTimeout = 50;
        }
        /// <summary>The next datagram, or null within the timeout.</summary>
        public byte[] Receive(int timeoutMs = 50)
        {
            _u.Client.ReceiveTimeout = timeoutMs;
            try { IPEndPoint ep = null; return _u.Receive(ref ep); }
            catch (SocketException) { return null; }
        }
        public void Dispose() => _u.Dispose();
    }
}
