# Roadmap

Where Interstate '76 everywhere is going, in three tiers. The live state is on GitHub, not in this file:

- **Project board** "i76-everywhere roadmap": the repo's [Projects tab](https://github.com/therealjkvalentine/i76-everywhere/projects)
  (columns Backlog / Now / Next / Later / Done; fields Evidence, Area, Effort).
- **Milestones**: [v0.8.0, v0.9, v1.0, Later](https://github.com/therealjkvalentine/i76-everywhere/milestones).
- **Issues**: [open](https://github.com/therealjkvalentine/i76-everywhere/issues), and
  [done](https://github.com/therealjkvalentine/i76-everywhere/issues?q=is%3Aissue+is%3Aclosed) (each closed issue links its record).
- **Ideas to vote on**: [Discussions > Ideas](https://github.com/therealjkvalentine/i76-everywhere/discussions/categories/ideas).

How the labels, milestones and records fit together: [docs/process/PROCESS.md](docs/process/PROCESS.md).

## Milestones

| milestone | what it means |
|---|---|
| **v0.8.0** | the current draft: Patch Kit polish, Nitro without a compiler, the player settings file, issue forms, the Mac Kit |
| **v0.9** | builder-testers: the first outside builders on Windows, Mac and Steam Deck; an internet-play option; a working feedback loop |
| **v1.0** | after the first feedback round: what outside testers found is fixed or ruled on |
| **Later** | wanted, no date |

## Tier 1: shipping and measured

Built, and backed by a measurement in a record (`evidence/measured`). What ships today is in the
[release notes](docs/release/) and the closed issues. Open work in this tier is mostly bugs and checks on new hardware:

- [#1](https://github.com/therealjkvalentine/i76-everywhere/issues/1) host's mission stalls while a joiner is in a co-op game
- [#2](https://github.com/therealjkvalentine/i76-everywhere/issues/2) Nitro at 1920x1080: odd first frame, enlarged HUD
- [#6](https://github.com/therealjkvalentine/i76-everywhere/issues/6) dgVoodoo 2.87.5 in every Nitro download (Windows 11)
- [#7](https://github.com/therealjkvalentine/i76-everywhere/issues/7) Mac: Nitro capped at 24 fps
- [#8](https://github.com/therealjkvalentine/i76-everywhere/issues/8) Mac Kit: the first build by a person
- [#27](https://github.com/therealjkvalentine/i76-everywhere/issues/27) Steam Deck rumble: does it reach your hands?

## Tier 2: designed

A written design or a spike exists, nothing measured end to end yet (`evidence/designed`):

- [#11](https://github.com/therealjkvalentine/i76-everywhere/issues/11) internet play through a hosted relay (works on a LAN; NAT test next)
- [#10](https://github.com/therealjkvalentine/i76-everywhere/issues/10) Nitro sessions stay compatible with the community lobby
- [#24](https://github.com/therealjkvalentine/i76-everywhere/issues/24) a render-size key on the Mac
- [#17](https://github.com/therealjkvalentine/i76-everywhere/issues/17) a measured 120 Hz+ tier for fast machines
- [#29](https://github.com/therealjkvalentine/i76-everywhere/issues/29) force feedback, shakers and motion on real hardware
- [#19](https://github.com/therealjkvalentine/i76-everywhere/issues/19) a mip chain for textures

## Tier 3: ideas

Big enough that they should only be built if people want them (`kind/idea`). Each has a post in Discussions > Ideas; upvote it.

- [#15](https://github.com/therealjkvalentine/i76-everywhere/issues/15) split-screen local co-op ([vote](https://github.com/therealjkvalentine/i76-everywhere/discussions/85))
- [#14](https://github.com/therealjkvalentine/i76-everywhere/issues/14) 16-player melee ([vote](https://github.com/therealjkvalentine/i76-everywhere/discussions/86))
- [#16](https://github.com/therealjkvalentine/i76-everywhere/issues/16) I'76 HD edition ([vote](https://github.com/therealjkvalentine/i76-everywhere/discussions/87))

## How to vote or file

- **Vote**: upvote a post in [Discussions > Ideas](https://github.com/therealjkvalentine/i76-everywhere/discussions/categories/ideas),
  or add a reaction to an issue. New idea: start a post in Ideas.
- **Report a problem**: [new issue](https://github.com/therealjkvalentine/i76-everywhere/issues/new/choose); the forms say which
  logs to attach.
- A maintainer's agent reads new issues and posts and may reply; the developer decides what gets built.
