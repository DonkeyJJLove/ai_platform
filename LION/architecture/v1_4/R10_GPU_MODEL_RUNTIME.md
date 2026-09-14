# R10 — GPU i lokalny model na MOON

**Stan:** CURRENT_AS_OF_OBSERVATION / kandydat dokumentacyjny R10. Ten dokument nie nadaje authority.

Świeży pomiar falsyfikuje wcześniejsze uproszczenie „GPU not observed from WSL = no GPU”. Fizyczny MOON posiada `NVIDIA GeForce RTX 5090` o UUID `GPU-bf2260b0-7c5c-89df-7571-49e6eefb6bb9`, 32607 MiB VRAM, sterownik 591.44 i CUDA driver API 13.1. Bieżący link PCIe jest Gen5 x16. Wszystkie cztery logiczne środowiska WSL (`MOON`, `LION-AUTH-LAB`, `LAB-UBUNTU`, `LAB-DEBIAN`) widzą `/dev/dxg`, `libcuda.so.1`, NVML i ten sam UUID GPU. Jednocześnie wszystkie mają ten sam boot ID `58008236-23d6-48d9-a501-7e13b2b8c7b6`; jest to jedna fizyczna domena GPU, nie cztery niezależne material executors.

Exact lokalny model pozostaje `gpt-oss-20b-MXFP4.gguf` o SHA-256 `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`. Runtime to llama.cpp build 10809 / commit `5266f24da`, endpoint `127.0.0.1:8772`, context 4096, jeden slot. Command line wiąże `--device Vulkan0 -ngl 99`; Windows `nvidia-smi` obserwuje PID 40308 jako proces GPU. Runtime nie jest CPU-only.

Bounded benchmark bez zmiany konfiguracji: 91 prompt tokens + 300 completion tokens, wall time 0.956463 s; prompt ~1097.95 tok/s, generation ~348.32 tok/s. Podczas próby zaobserwowano około 13660 MiB VRAM used, maksymalnie 85% GPU utilization, 36°C i 410.52 W. Są to wartości zmierzone dla tej konkretnej próby, nie prognoza ogólnej wydajności.

RCA wcześniejszej obserwacji: `STALE_OR_INSUFFICIENT_GPU_OBSERVATION`, primary cause `OBSERVATION_COMMAND_INSUFFICIENT`. Brak PyTorch/CuPy w WSL nie jest dowodem braku CUDA: `/dev/dxg`, sterownik, libcuda i NVML są obecne.

Security finding: llama-server jest związany z loopback, ale raportuje CORS `*` i brak API key. Dlatego port 8772 nie powinien być bezpośrednim interfejsem użytkowym ani tool endpointem. R10 LLIP ma stanowić lokalną warstwę mediacji; model pozostaje proposal-only i nie dostaje shell/push/merge/delete/credentials/service-admin/runtime-authority.
