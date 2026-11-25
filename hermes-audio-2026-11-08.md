# Chromium offline audio: measured cause and non-rebuild fix

Date: 2026-11-08. Scope: this Linux VM, headed Chrome under Xvfb; no Chromium rebuild and no StealthXGM source edits.

## Conclusion

`124.04347776696522` is genuine, unmodified Chrome for Testing 159 output on this VM. It is also the native output of the tested 152, 156 and 157 builds. CreepJS's known-value table does not contain this RustFFT-era output. The nine highlighted digits are a stale-reference mismatch, not evidence that a sound card is missing or that this checksum was spoofed.

The exact cause is Chromium's native FFT backend change from PFFFT to RustFFT. This was isolated on the SAME Chrome 152 executable: disabling its real native FFT feature restores the complete old buffer byte-for-byte and changes the unmodified CreepJS Audio sum from nine bold-fail digits to zero.

ONE recommended solution for passing this unchanged CreepJS reference without rebuilding: use Chrome for Testing `152.0.7977.82` as the kernel with `--disable-blink-features=WebAudioRustFft`. This is measured below, not an untested flag suggestion. The same flag does not work on 159, where the legacy path has been removed.

## Measurements

All listed builds ran headed under Xvfb with fresh profiles and no fingerprinting extensions or API overrides. Chrome was launched directly; Playwright connected over CDP only to evaluate the native graph. Actual versions came from both `--version` and `Browser.getVersion`.

Environment: Linux x86-64, AMD EPYC 9D64 CPU, KVM; `/dev/snd` and `/dev/dri` are absent. No sound card or GPU was added. The native render used one channel, 5000 frames, 44100 Hz, triangle oscillator at 10000 Hz, compressor threshold -50, knee 40, attack 0, default ratio 12 and release 0.25.

| Chrome for Testing version | Binary provenance | CreepJS sampleSum, last 500 frames | Sum of all 5000 frames | In KnownAudio for measured gain? |
|---|---|---:|---:|---|
| 159.0.8148.0 | Existing kernel AND fresh official download | 124.04347776696522 | 1085.3711101742233 | No |
| 156.0.8078.4 | Existing CfT kernel, clean profile | 124.04347776696522 | 1085.3711101742233 | No |
| 157.0.8103.38 | Fresh official download | 124.04347776696522 | 1085.3711101742233 | No |
| 152.0.7977.82 | Fresh official download, default backend | 124.04347776696522 | 1085.3711101742233 | No |
| 151.0.7922.138 | Fresh official download | 124.04347527516074 | 1085.371121346027 | Yes |
| 142.0.7444.175 | Fresh official download | 124.04347527516074 | 1085.371121346027 | Yes |
| 131.0.6778.264 | Fresh official download | 124.04347527516074 | 1085.371121346027 | Yes |
| 120.0.6099.109 | Fresh official download | 124.04347527516074 | 1085.371121346027 | Yes |

Plain system Chromium: not installed. PATH, installed-package queries and binary discovery found no plain system Chromium/Google Chrome. `/opt/meta-chromium/chrome` identifies itself as custom Muse Browser 157; it was not misrepresented as an unmodified Chromium control.

Coverage verified programmatically: eight distinct versions, 13 fresh browser launches, 35 native probe renders and four actual CreepJS Audio DOM checks. Every listed default build had at least three repeated renders. Repeats were byte-identical; `copyFromChannel` matched `getChannelData`, and the first 100 frames were zero.

The table is NOT specific to one Chrome version: 120, 131, 142 and 151 all produce the same allowlisted buffer here. Switching only from 159 to 156 does not fix the mismatch. Native 151 does match the reference; native default 152 already produces the same unlisted checksum as 159.

### Two exact collector details

The published `creep.js` actually computes `sampleSum` over indices 4500 through 4999, NOT over the whole 5000-frame buffer. The whole-buffer sums are separately reported above.

Its graph branches from compressor to analyser AND destination, rather than serially through the analyser. Both graphs were tested on 159 and produced the exact same complete buffer, so that wording difference does not explain the failure.

The local CreepJS bundle and freshly retrieved published bundle were byte-identical:

    SHA-256: 80f43f364bd973bc03cb5b82de033ce28b2bbb145cb04237632a46ef040a92be

## Exact cause: native FFT implementation, not audio hardware

Chromium constructs the oscillator's band-limited waveform tables using an inverse FFT, then normalizes them. Changing that implementation changes the oscillator's Float32 samples before they enter the compressor. The analyser also uses FFT. Thus this is not merely a change to the displayed analyser frequency sum.

The tagged 151 source uses the platform FFT path. The tagged 152 source retains both paths and selects RustFFT through `WebAudioRustFft`; the feature is declared stable. Tagged 156 and 159 call RustFFT unconditionally. RustFFT has its own native CPU/SIMD planner, including AVX/FMA paths; pure CPU DSP does not imply identical low bits across different DSP implementations.

Chromium explicitly accepted this fingerprint change. Its RustFFT reland commit, `0d3c3f478f9c4d1c5e2ce9f9c6fae6c0f19a41a0`, states:

> After internal discussion, the fingerprinting issue which caused the revert of the original change was determined to not be a blocker. This reland completely removes the fingerprinting test.

The subsequent legacy-path removal is commit `39e79486d2f63738c0f047f9b709989623fb8906`.

The numerical difference between the two CreepJS sums is only `0.00000249180448`. Across the complete buffers, 2888 of 5000 frames differ; the maximum absolute per-frame difference is `8.940696716308594e-08`. CreepJS compares exact known values and decorates differing decimal characters; nine highlighted characters are not nine independent audio failures.

## Same-executable A/B proof and actual CreepJS result

No compressor parameter, sample rate, sound device, API implementation or executable was changed between the two 152 runs. Only the native backend selector changed.

| Build / native selector | Last-500 sum | Actual CreepJS bold-fail digits in sum | Actual Audio hash class |
|---|---:|---:|---|
| 151.0.7922.138, default | 124.04347527516074 | 0 | hash |
| 152.0.7977.82, default RustFFT | 124.04347776696522 | 9 | hash |
| SAME 152.0.7977.82, WebAudioRustFft disabled | 124.04347527516074 | 0 | hash |
| 159.0.8148.0, default | 124.04347776696522 | 9 | hash |

Additional 159 control with `--disable-blink-features=WebAudioRustFft`: still `124.04347776696522`, with the identical RustFFT buffer. This obsolete feature flag is not a 159 fix.

The same 152 ELF was used for both sides of the A/B:

    Executable SHA-256:
    115ee0fc6d26768ec757db2b0c6f54554dece46b59e96c7eca653c944db7f3de

Complete 5000-frame Float32 buffer SHA-256 values:

    Native RustFFT: 152 default / 156 / 157 / 159
    0d6f33df90bb7c70e12339d9c128f988eee40e58e1c53912b0df4445f927e95e

    Native PFFFT: 120 / 131 / 142 / 151 / same 152 with flag disabled
    2909ad9a94af162965434a66c34b7033cc31de48f4e13013a1197b9bd0e28085

Existing 159 and freshly downloaded official 159 executable hashes also matched exactly:

    940e7d793ac6b25a3cb2e5f4e21d1a9db94d954504c7b849ecfc0ec2b0ec311d

### What the nine digits actually mean

`KnownAudio` is keyed by compressor gain, not Chrome version. For gain `-20.538288116455078`, the first presentation reference is `124.04347518575378`. When the measured sum is absent from that array, `audioHTML` highlights differing characters.

The separate locked-pattern predicate is:

    knownPattern && !knownPattern.includes(sampleSum)

The genuine RustFFT tuple is absent from that locked table:

    gain: -20.538288116455078
    freq: 164539.10749435425
    time: 502.59992877283

Therefore this tuple does not itself trigger that `LowerEntropy.AUDIO` predicate. In the actual 159 and 152 page checks the Audio container was `relative col-four`, not `rejected`, and its hash class was plain `hash`, not `lies` or `bold-fail`. The nine bold digits are the sum's known-value decoration, distinct from CreepJS's tampering/noise rejection.

## Recommended solution: one kernel and one native selector

Use official Chrome for Testing `152.0.7977.82` and disable its native RustFFT selector:

    --disable-blink-features=WebAudioRustFft

If that switch already contains `AutomationControlled`, append the feature to the existing comma-separated value rather than supplying competing duplicate switches:

    --disable-blink-features=AutomationControlled,WebAudioRustFft

Official full-browser Linux archive:

https://storage.googleapis.com/chrome-for-testing-public/152.0.7977.82/linux64/chrome-linux64.zip

Measured result on this VM: native PFFFT buffer restored byte-for-byte, CreepJS sum `124.04347527516074`, zero highlighted sum digits, matching copy/data samples. No JavaScript checksum substitution or AudioBuffer hook is involved.

On 159 the PFFFT selection path is gone; the tested selector has no effect. Keeping that exact 159 kernel while restoring the old native FFT implementation would require changing its native implementation/build. That was not attempted. The selected 152 kernel-plus-selector solution avoids rebuilding and was exercised against the unchanged CreepJS page.

This is a recommendation backed by clean-kernel tests; no StealthXGM integration, existing profile changes or existing kernel replacement was performed by this investigation.

## Evidence and reproduction

Probe, downloaded official binaries, provenance files, browser logs, complete Float32 buffers and JSON results:

    /home/hatch/.hermes/cache/scratch/hermes-audio-20261108-660464f0d3fa/
    audio_probe.py
    verify_creep_ui.py
    measurements.jsonl
    verification-summary.json
    provenance-<version>.json
    research/source-excerpts.txt

Reproduce the recommended selector and inspect the unchanged CreepJS Audio DOM:

    TMPDIR=/home/hatch/.hermes/cache/scratch xvfb-run -a /usr/bin/python3 /home/hatch/.hermes/cache/scratch/hermes-audio-20261108-660464f0d3fa/verify_creep_ui.py 152.0.7977.82 --label-prefix repeat-pffft --extra-arg=--disable-blink-features=WebAudioRustFft

Authoritative source references:

- RustFFT reland and explicit fingerprinting decision: https://chromium-review.googlesource.com/c/chromium/src/+/7945521
- Legacy FFT removal: https://chromium-review.googlesource.com/c/chromium/src/+/8293199
- Tagged 152 native selector: https://chromium.googlesource.com/chromium/src/+/refs/tags/152.0.7977.82/third_party/blink/renderer/platform/audio/fft_frame.cc#75
- Tagged 159 unconditional RustFFT: https://chromium.googlesource.com/chromium/src/+/refs/tags/159.0.8148.0/third_party/blink/renderer/platform/audio/fft_frame.cc#64
- Oscillator inverse-FFT waveform construction: https://chromium.googlesource.com/chromium/src/+/refs/tags/159.0.8148.0/third_party/blink/renderer/modules/webaudio/periodic_wave_handler.cc#348
- CreepJS collector, KnownAudio and presentation predicates: https://github.com/abrahamjuliot/creepjs/blob/10aa6724cd33a1015db1574211890518cd04f0cc/docs/creep.js#L2470-L2908
- Official binary metadata retrieved for these downloads: https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json

DONE: genuine 159 output and stale CreepJS reference established; native FFT backend isolated; one non-rebuild kernel-plus-selector solution measured; no StealthXGM code edits.
