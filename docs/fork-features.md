# Front page of this fork — the words

The front page block of `README.md` is generated: the numbers come from git, the state of every pull
request comes from the GitHub API, and the words come from this file. `scripts/fork-pr-table.sh`
assembles the three. Edit this file, run `git fork-refresh`, and the front page follows.

Sections are delimited by `<!-- intro -->`, `<!-- feature: id -->` and `<!-- closing -->`, each ended by
`<!-- end -->`. Inside a feature section, `<!-- image -->` is where the diagram goes (the generator
skips it when the file is missing, so no broken image is ever published) and `<!-- bullets -->` is where
the generated bullets are appended: the size of the change, the documentation link and the state upstream.

The sentence that says how much of this fork is in an official WanGP release is not written here. It is
counted from the state of every pull request, and from the upstream release each acceptance went into,
because a typed claim of that kind goes false the day upstream accepts the first one.

<!-- intro -->
**This is a personal fork of [WanGP](https://github.com/deepbeepmeep/WanGP) by
[DeepBeepMeep](https://github.com/deepbeepmeep)** — the app, its name, its docs, its models and its licence are
the upstream project's, and upstream is the canonical project: see [wangp.ai](https://wangp.ai). This repository
is **not affiliated with, sponsored or endorsed** by the upstream author.
<!-- end -->

<!-- feature: latents -->
**What it is.** Keep the latents a generation produced, and reuse them: decode them again, or continue from
them. Wan 2.1/2.2, LongCat, LTX-2, MiniMax H3 and Magi Human.

**Why it is worth having.** The diffusion is the expensive part, and upstream discards its latents once the
video is written. With the latents on disk, changing the decoder, the scale, the colour or the schedule stops
costing a full re-generation, and a shot you like stops being a one-off: you branch a new generation from the
exact latent the model ended on, seed and work preserved.

<!-- image -->

The sidecar is a plain `torch.save` payload, so a generation you did not plan for is scriptable too:

```
my_shot.mp4
my_shot_latent.pt        python -c "import torch; d = torch.load('my_shot_latent.pt'); print(d.keys())"
```

<!-- bullets -->
<!-- end -->

<!-- feature: filenames -->
**What it is.** One default filename template per model, honoured at generation time and checked before the
generation starts.

**Why it is worth having.** A folder of `ltx2_1280x720_1234.mp4` says nothing a week later. The template writes
in what produced the file, using the *effective* output values: a task upsampled to 1440p is named 1440p, not
the resolution you clicked. A template that cannot be honoured is reported when you generate, not halfway
through the video.

<!-- image -->

- 20 keywords — `{model}`, `{date(…)}`, `{width}`, `{height}`, `{fps}`, `{scale}`, `{steps}`, `{seed}`,
  `{prompt(40)}`, `{teacache}`, `{temporal_upsampling}` … — and any of them takes a Python format spec,
  `{fps:.0f}`, `{scale:.2f}`

<!-- bullets -->
<!-- end -->

<!-- feature: dlss -->
**What it is.** Temporal upscaling beyond x2 on Linux — x3/x4 on RTX 40 and RTX 50, up to x6 on RTX 50 — plus
Frame Generation whose worker builds natively on Linux: no Windows, no Wine.

**Why it is worth having.** On Linux the *Temporal Upsampling* menu stopped at x2, and the frame-generation
binaries existed only for Windows, so the same graphics cards gave smooth high-resolution output under Windows
and not under Linux. They do now, from the same menu, and on a two-GPU host the run prints which card makes the
frames.

| | upstream | this fork |
|---|---|---|
| temporal upscaling on Linux | up to x2 | x3, x4, up to x6 on RTX 50 |
| frame generation on Linux | Windows binaries only | built natively, `scripts/build_dlssg_worker_linux.sh` |
| the DLSS SDK runtime files | fetched by hand | `scripts/install_dlss5.sh` |
| a saved choice in the menu | reset by the model menus | kept |
| a two-GPU host | the worker follows noone | prints the card that makes the frames |

- the worker is `scripts/dlssg_worker_linux/`, 1 196 lines of C++ (a Vulkan port, MIT, notice kept), built on
  your machine because the NVIDIA runtime licence forbids redistributing it

<!-- bullets -->
<!-- end -->

<!-- closing -->
**Install:** as upstream — `git clone https://github.com/abencq/Wan2GP.git && cd Wan2GP && python wgp.py`
(Windows: `run.bat`). Your models, settings and outputs are laid out as upstream puts them, so switching either
way keeps them.

> Per section 4.1 of the [WanGP Community License 2.0](LICENSE.txt), this fork states its modifications and
> their dates in **[docs/FORK.md](docs/FORK.md)**, and keeps the upstream licence, the in-tree notices and the
> [third-party licence texts](docs/third_party_licenses/).
<!-- end -->
