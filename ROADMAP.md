# Flight Engineer Roadmap

This file keeps promising backend work discoverable without coupling the
stable Hermes plugin API to unvalidated runtimes.

## DwarfStar (`antirez/ds4`) Driver Investigation

Status: back pocket; research only; no production dependency.

Source: <https://github.com/antirez/ds4>

DwarfStar is a deliberately narrow inference engine for selected DeepSeek V4
and GLM models. It uses project-produced GGUFs rather than acting as a general
GGUF runner. The project currently advertises Metal, generic CUDA, ROCm,
multi-GPU serving, pipeline execution across systems, compressed KV, and SSD
streaming. It is beta and fast-moving.

Why it may matter to Flight Engineer:

- It could make a much larger routed-expert model practical as a specialist
  backend when RAM, VRAM, or multiple machines must be combined.
- Its loopback HTTP server could fit the stable Hermes named-provider contract.
- Its integrated model, prompt, tool, KV, server, and agent tests match Flight
  Engineer's preference for accepted configurations rather than loose flags.

Questions to answer before writing an adapter:

1. Does `cuda-generic` work correctly and usefully on one RTX 3090, rather than
   only the project's DGX Spark and multi-GPU targets?
2. What model, host-RAM, VRAM, SSD capacity, prefill, generation, and first-token
   measurements result from the smallest worthwhile DeepSeek/GLM profile?
3. Is SSD streaming implemented and performant on Linux/CUDA, or effectively a
   Metal-first path today?
4. Does `ds4-server` provide the OpenAI-compatible chat, streaming, tool-call,
   cancellation, model-list, metrics, and vision behavior Hermes needs?
5. Can it coexist with production TTS and remain inside the same health,
   in-flight-request, acceptance, rollback, and audit contract as llama.cpp?
6. Are its project-specific GGUF licenses and redistribution terms acceptable
   for a public Flight Engineer example profile?

Acceptance gate:

- Build from a pinned commit in an isolated lab.
- Use exact model revision, hashes, quantization, and measured storage.
- Run direct API, Hermes text/tool/JSON, MoA reference, cancellation, context,
  concurrency, and shared-GPU tests.
- Compare against the current llama.cpp daily driver on latency, quality,
  memory, power, and recovery behavior.
- Add a `ds4` driver only if it can implement the existing Flight Engineer
  status/list/use/rollback contract without special cases in the Hermes plugin.

## llama.cpp GLM-5.3-Flash Support

Status: upstream pull request open; track before testing.

Source: <https://github.com/ggml-org/llama.cpp/pull/27773>

PR `#27773` adds GLM-5.3-Flash (`glm5-next`) text and vision support to
llama.cpp. This is strategically important because Flight Engineer already has
a llama.cpp backend, so a validated GLM profile could avoid adding another
runtime driver. The proposed model is a 320B hybrid architecture with KDA, DSA,
mHC, and routed MoE layers. The implementation deliberately keeps about 1 GB
of precision-sensitive tensors unquantized.

Known constraints from the open PR:

- Multiple sequences require unified KV.
- Vision uses a new GLM5V preprocessing path and compatible projector.
- MTP is not part of this PR; it is tracked separately in llama.cpp PR
  `#27917`.
- GGUF architecture and tensor naming changed during review. Use only a quant
  explicitly converted for the pinned runtime commit.
- Community testing shows the architecture can run with 24 GB VRAM plus large
  host RAM, but that is not evidence that Jarvis's specific 3090/RAM/storage
  combination will meet latency or co-residency targets.

Evaluation order:

1. Wait for merge or pin a reviewed commit in an isolated branch. Never replace
   the production llama.cpp image with an unpinned PR build.
2. Confirm an exact compatible GGUF/projector revision, total disk size, host
   RAM requirements, license, and checksum before downloading.
3. Measure storage-backed or CPU-offloaded loading, prefill, generation,
   first-token latency, context growth, and 24 GB VRAM behavior.
4. Run Flight Engineer's normal text, strict JSON, tools, vision, cancellation,
   concurrency, MoA-reference, TTS co-residency, and rollback acceptance.
5. Compare the same GLM quant under DwarfStar when both runtimes offer a viable
   configuration. Prefer llama.cpp if quality and latency are comparable because
   it preserves the existing driver and operational surface.
