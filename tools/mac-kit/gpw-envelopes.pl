#!/usr/bin/perl
# gpw-envelopes.pl - the rumble envelope table (rumble-envelopes.ini) from the player's own I76.ZFS, in Perl so that the
# Mac Kit can build it on the Mac (macOS ships perl; python3 and liblzo2 are not guaranteed there). The same table
# tools/gpw-envelopes.py writes: one "name=v0,v1,..." line per .gpw effect sound, values 0-100 = windowed RMS of the
# sound, peak-normalised, 25 ms windows over the first 1.5 s. The outputs are byte-identical (checked 2026-11-04 on the
# GOG Gold I76.ZFS: 123 / 123 lines). The table is derived from the player's files on the player's machine; the kit
# does not ship it.
#
#   perl gpw-envelopes.pl <I76.ZFS | game folder> [--out rumble-envelopes.ini] [--window-ms 25] [--max-s 1.5]
#
# .gpw = a 28-byte "GAS0" wrapper + RIFF/WAVE (PCM mono 8-bit 11025 Hz in the stock set; 16-bit handled).
# ZFS entries are stored (0) or LZO1X (2) / LZO1Y (4) compressed (tools/zfs_extract.py has the layout); the LZO
# decoder below is a port of tools/lzo.py.
use strict; use warnings; use POSIX qw(floor);

my ($src, $out, $window_ms, $max_s) = (undef, 'rumble-envelopes.ini', 25, 1.5);
while (@ARGV) {
    my $a = shift @ARGV;
    if    ($a eq '--out')       { $out = shift @ARGV }
    elsif ($a eq '--window-ms') { $window_ms = 0 + shift @ARGV }
    elsif ($a eq '--max-s')     { $max_s = 0 + shift @ARGV }
    else                        { $src = $a }
}
die "usage: gpw-envelopes.pl <I76.ZFS | game folder> [--out file]\n" unless defined $src;
if (-d $src) {
    opendir(my $dh, $src) or die "$src: $!"; my ($z) = grep { lc($_) eq 'i76.zfs' } readdir($dh); closedir $dh;
    die "no I76.ZFS in $src\n" unless defined $z; $src = "$src/$z";
}
open(my $fh, '<:raw', $src) or die "$src: $!"; my $data = do { local $/; <$fh> }; close $fh;

# ---- ZFS directory: header 0x1C, then blocks of <next u32> + per_dir entries of 36 bytes ----------------------------
my ($magic, $version, undef, $per_dir, $total) = unpack('a4 V V V V', $data);
die "$src is not a ZFSF v1 archive\n" unless $magic eq 'ZFSF' && $version == 1;
my @entries; my $block = 0x1C;
while (@entries < $total) {
    my $next = unpack('V', substr($data, $block, 4)); my $pos = $block + 4;
    my $n = $total - @entries; $n = $per_dir if $n > $per_dir;
    for (1 .. $n) {
        my ($raw_name, $off, undef, $len, undef, $comp, $d0, $d1, $d2) = unpack('a16 V V V V C C C C', substr($data, $pos, 36));
        (my $name = $raw_name) =~ s/\0.*//s; $name = lc $name;
        push @entries, [$name, $off, $len, $comp, $d0 | ($d1 << 8) | ($d2 << 16)];
        $pos += 36;
    }
    $block = $next;
}

# ---- LZO1X / LZO1Y decoder (LZO 1.00 stream), a port of tools/lzo.py ------------------------------------------------
sub lzo_decompress {
    my ($s, $variant, $out_len) = @_;
    my @src = unpack('C*', $s); my $ip = 0; my $o = ''; my $m2 = $variant eq '1x' ? 0x800 : 0x400;
    my $copy = sub { my ($mpos, $cnt) = @_; die "lookbehind\n" if $mpos < 0; $o .= substr($o, $mpos + $_, 1) for 0 .. $cnt - 1; };
    my $state = 'next'; my $t = $src[$ip]; my $mpos;
    if ($t > 17) {
        $ip++; $t -= 17;
        if ($t < 4) { $state = 'match_next' } else { $o .= substr($s, $ip, $t); $ip += $t; $state = 'first_literal_run' }
    }
    while (1) {
        if ($state eq 'next') {
            $t = $src[$ip++];
            if ($t >= 16) { $state = 'match'; next }
            if ($t == 0) { while ($src[$ip] == 0) { $t += 255; $ip++ } $t += 15 + $src[$ip++] }
            $o .= substr($s, $ip, $t + 3); $ip += $t + 3; $state = 'first_literal_run'; next;
        }
        if ($state eq 'first_literal_run') {
            $t = $src[$ip++];
            if ($t >= 16) { $state = 'match'; next }
            $mpos = length($o) - (1 + $m2) - ($t >> 2) - ($src[$ip++] << 2);
            $copy->($mpos, 3); $state = 'match_done'; next;
        }
        if ($state eq 'match') {
            if ($t >= 64) {
                if ($variant eq '1x') { $mpos = length($o) - 1 - (($t >> 2) & 7) - ($src[$ip++] << 3); $t = ($t >> 5) - 1 }
                else                  { $mpos = length($o) - 1 - (($t >> 2) & 3) - ($src[$ip++] << 2); $t = ($t >> 4) - 3 }
            } elsif ($t >= 32) {
                $t &= 31;
                if ($t == 0) { while ($src[$ip] == 0) { $t += 255; $ip++ } $t += 31 + $src[$ip++] }
                $mpos = length($o) - 1 - (($src[$ip] >> 2) + ($src[$ip + 1] << 6)); $ip += 2;
            } elsif ($t >= 16) {
                $mpos = length($o) - (($t & 8) << 11); $t &= 7;
                if ($t == 0) { while ($src[$ip] == 0) { $t += 255; $ip++ } $t += 7 + $src[$ip++] }
                $mpos -= ($src[$ip] >> 2) + ($src[$ip + 1] << 6); $ip += 2;
                if ($mpos == length($o)) {
                    die sprintf("decoded %d bytes, expected %d\n", length($o), $out_len) if defined $out_len && length($o) != $out_len;
                    return $o;   # EOF marker
                }
                $mpos -= 0x4000;
            } else {
                $mpos = length($o) - 1 - ($t >> 2) - ($src[$ip++] << 2);
                $copy->($mpos, 2); $state = 'match_done'; next;
            }
            $copy->($mpos, $t + 2); $state = 'match_done'; next;
        }
        if ($state eq 'match_done') { $t = $src[$ip - 2] & 3; $state = $t == 0 ? 'next' : 'match_next'; next }
        if ($state eq 'match_next') { $o .= substr($s, $ip, $t); $ip += $t; $t = $src[$ip++]; $state = 'match'; next }
    }
}

# ---- GPW -> centred samples; windowed RMS; peak-normalised 0-100 (the same arithmetic order as the Python) ----------
sub decode_gpw {   # returns (rate, samples arrayref) or dies
    my ($p) = @_;
    my $riff = index($p, 'RIFF'); die "no RIFF chunk\n" if $riff < 0;
    my $pos = $riff + 12; my ($fmt_tag, $width, $rate, $channels, $raw);
    while ($pos + 8 <= length $p) {
        my ($id, $size) = unpack('a4 V', substr($p, $pos, 8)); $pos += 8;
        if ($id eq 'fmt ') { ($fmt_tag, $channels, $rate, undef, undef, my $bits) = unpack('v v V V v v', substr($p, $pos, 16)); $width = $bits >> 3 }
        elsif ($id eq 'data') { $raw = substr($p, $pos, $size); last }
        $pos += $size + ($size & 1);
    }
    die "no fmt chunk\n" unless defined $fmt_tag; die "no data chunk\n" unless defined $raw;
    die "unknown format tag $fmt_tag\n" unless $fmt_tag == 1 || $fmt_tag == 0xFFFE;   # PCM only, as Python's wave module
    my @samples;
    if    ($width == 1) { @samples = map { ($_ - 128) / 128.0 } unpack('C*', $raw) }
    elsif ($width == 2) { @samples = map { $_ / 32768.0 } unpack('s<*', $raw) }
    else { die "unhandled sample width $width\n" }
    return ($rate, \@samples);
}
sub round_half_even { my $x = shift; my $f = floor($x); my $r = $x - $f; return $r > 0.5 ? $f + 1 : $r < 0.5 ? $f : ($f % 2 == 0 ? $f : $f + 1) }
sub envelope {
    my ($rate, $samples) = @_;
    my $win = int($rate * $window_ms / 1000); $win = 1 if $win < 1;
    my $n = int($rate * $max_s); $n = @$samples if $n > @$samples;
    my @out;
    for (my $i = 0; $i < $n; $i += $win) {
        my $end = $i + $win; $end = $n if $end > $n; my $sum = 0.0;
        $sum += $samples->[$_] * $samples->[$_] for $i .. $end - 1;
        push @out, ($sum / ($end - $i)) ** 0.5;
    }
    my $peak = 0; for (@out) { $peak = $_ if $_ > $peak }
    return () if $peak <= 0;
    return map { round_half_even(100 * $_ / $peak) } @out;
}

(my $base = $src) =~ s{.*[/\\]}{};
my @lines = ('; rumble envelope table generated by tools/gpw-envelopes.py',
             "; source=$base window_ms=$window_ms max_s=$max_s scale=0-100 (RMS, peak-normalized)",
             '; one value per window; play one per tick, scale motor amplitude.');
my ($ok, $bad) = (0, 0);
for my $e (sort { $a->[0] cmp $b->[0] } grep { $_->[0] =~ /\.gpw$/ } @entries) {
    my ($name, $off, $len, $comp, $dlen) = @$e;
    my @env;
    eval {
        my $payload = $comp == 0 ? substr($data, $off, $len) : lzo_decompress(substr($data, $off, $len), $comp == 2 ? '1x' : '1y', $dlen);
        my ($rate, $samples) = decode_gpw($payload);
        @env = envelope($rate, $samples);
        1;
    } or do { (my $m = $@) =~ s/\n$//; print STDERR "  skip $name: $m\n"; $bad++; next };
    if (@env) { push @lines, substr($name, 0, -4) . '=' . join(',', @env); $ok++ }
}
open(my $oh, '>', $out) or die "$out: $!"; binmode $oh; print $oh join("\n", @lines), "\n"; close $oh;
print "wrote $out: $ok envelopes ($bad skipped)\n";
