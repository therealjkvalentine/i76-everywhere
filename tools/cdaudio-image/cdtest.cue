REM Minimal 2-track AUDIO CD image, for validating that a virtual drive
REM exposes CD-DA to MCI's "cdaudio" device. Track 1 = 440 Hz, track 2 = 660 Hz.
FILE "cdtest.bin" BINARY
  TRACK 01 AUDIO
    INDEX 01 00:00:00
  TRACK 02 AUDIO
    INDEX 01 00:04:00
