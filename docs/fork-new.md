| Feature | What it does | Upstream |
|---|---|---|
| Continue Video (MiniMax H3) | the joins between sliding windows keep their timing when the soundtrack ends a little before the last frame | [#2478](https://github.com/deepbeepmeep/WanGP/pull/2478) |
| Empty audio | a job that ends up with no audio keeps its video | [#2482](https://github.com/deepbeepmeep/WanGP/pull/2482) |
| Console Log Stamps | the time of day at the start of the console lines WanGP prints, `--log-timestamp` (default: off) | [#2568](https://github.com/deepbeepmeep/WanGP/pull/2568) |
| Console Guard | the terminal is taken as found and returned to the shell at the end of a run, `--console-guard` (default: on) | [#2526](https://github.com/deepbeepmeep/WanGP/pull/2526) |

- **Continue Video (MiniMax H3):** continuing a video no longer stops when its soundtrack ends a little before the last frame: WanGP asks the model for no more of that closing audio than the frames it can regenerate, and keeps the source audio up to where it ends, so the joins between sliding windows keep their timing.

- **Empty audio:** Saving audio that came out empty no longer crashes the save, so a job that ends up with no audio keeps its video.

- **Console Log Stamps:** WanGP puts the time of day at the start of the console lines it prints, for instance, `2026-10-12 15:06:41 | Model loaded: Wan 2.2 14B`. Added a new `--log-timestamp` option to stamp a run (default: off), a new `--log-timestamp-format` option for the format of the stamp (default: the full date and clock), and a new `--log-timestamp-sep` option for the separator between the stamp and the line (default: the pipe). Denoise, download and queue bars keep redrawing on the screen as they always did, with one stamp where each bar line starts. The stamps cover only lines that carry text, and in a terminal the line printed after Ctrl+C starts on its own line. A traceback takes the stamps off for good, so a crash dump and the prompt after it read clean. *Command Line Reference* in `docs/CLI.md` covers the rest.

- **Console Guard:** WanGP gives the terminal back to the shell when a run ends. The ffmpeg and TTS binaries read the keyboard on the terminal they share with the shell and turn echo, line editing and Ctrl+C off, and a run that ends on one of them leaves the shell prompt dead, with `reset` the only way back. WanGP now takes the terminal as it finds it and returns it in that state — at the end of a run, on Ctrl+C, on *Save and Quit* and on *Restart* — on Windows as well, and repairs a terminal that arrives broken. Added a new `--console-guard` option to leave the terminal alone (default: on), for a setup that owns the terminal already.
