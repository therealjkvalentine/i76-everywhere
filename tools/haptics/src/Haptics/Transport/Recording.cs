using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Haptics.Transport
{
    /// <summary>
    /// .i76rec: raw i76tel datagrams with host timestamps, the input to every offline run (HAPTICS-ARCHITECTURE 4.3
    /// "replays"; memory: retain raw captures, they outlive methods). Layout, little-endian:
    ///   "I76REC01"  u32 meta_len  meta_len bytes of UTF-8 JSON (source, created, note)
    ///   then records: f64 host_time_s  u32 len  len bytes (one datagram: frame + its events, any i76tel version)
    /// Python reader/writer: design/i76rec.py.
    /// </summary>
    public sealed class RecordingWriter : IDisposable
    {
        readonly BinaryWriter _w;
        public int Count;
        public RecordingWriter(string path, string metaJson = null)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
            _w = new BinaryWriter(File.Create(path));
            _w.Write(Encoding.ASCII.GetBytes("I76REC01"));
            var meta = Encoding.UTF8.GetBytes(metaJson ?? "{}");
            _w.Write((uint)meta.Length); _w.Write(meta);
        }
        public void Add(double hostTime, byte[] datagram, int len = -1)
        {
            if (len < 0) len = datagram.Length;
            _w.Write(hostTime); _w.Write((uint)len); _w.Write(datagram, 0, len);
            Count++;
        }
        public void Dispose() { _w.Flush(); _w.Dispose(); }
    }

    public sealed class RecordingReader
    {
        public string Meta;
        public readonly List<(double t, byte[] data)> Records = new List<(double, byte[])>();
        public static RecordingReader Load(string path)
        {
            var r = new RecordingReader();
            using (var br = new BinaryReader(File.OpenRead(path)))
            {
                var magic = Encoding.ASCII.GetString(br.ReadBytes(8));
                if (magic != "I76REC01") throw new InvalidDataException(path + " is not an .i76rec (magic '" + magic + "')");
                int ml = (int)br.ReadUInt32();
                r.Meta = Encoding.UTF8.GetString(br.ReadBytes(ml));
                while (br.BaseStream.Position + 12 <= br.BaseStream.Length)
                {
                    double t = br.ReadDouble(); int len = (int)br.ReadUInt32();
                    if (br.BaseStream.Position + len > br.BaseStream.Length) break;   // truncated tail (recorder killed): keep what is whole
                    r.Records.Add((t, br.ReadBytes(len)));
                }
            }
            return r;
        }
    }
}
