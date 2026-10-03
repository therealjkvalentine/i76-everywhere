#!/usr/bin/env python3
r"""h9_comfy_img2img.py - H9 probe: low-denoise SDXL img2img over an ESRGAN upscale, via a local ComfyUI API.
Sprint 2026-10-03, agent U6. Stdlib only (urllib); the ComfyUI server does the work.

Server used in the sprint (existing install, nothing installed; all I/O redirected into the work folder):
    C:\ComfyUI\venv\Scripts\python.exe C:\ComfyUI\main.py --listen 127.0.0.1 --port 8199 --disable-all-custom-nodes
        --fp8_e4m3fn-unet --input-directory  <work>\comfy\input --output-directory <work>\comfy\output
        --temp-directory <work>\comfy\temp --user-directory <work>\comfy\user --database-url sqlite:///<work>/comfy/user/comfyui.db
(--fp8_e4m3fn-unet: SDXL UNet weights stored in fp8 (~2.6 GB), computed in fp32 - Pascal has no usable fp16.)

    python h9_comfy_img2img.py --image IN.png --denoise 0.2 0.3 [--ckpt sd_xl_base_1.0.safetensors] [--seed 76]

Copies IN.png into the server's input folder, queues one prompt per denoise value, waits, prints output files.
Graph: CheckpointLoaderSimple -> LoadImage -> VAEEncodeTiled -> KSampler(dpmpp_2m karras, 20 steps, cfg 5,
denoise d, fixed seed) -> VAEDecodeTiled -> SaveImage. No ControlNet (no SDXL tile CN on disk), no IP-Adapter.
"""
import os, sys, json, time, shutil, argparse, urllib.request, uuid

POS = ("1997 hand-painted video game texture, airbrushed, limited palette, flat cel shading, matte, clean edges")
NEG = "photo, photorealistic, 3D render, bokeh, blur, noise, text, watermark, extra detail"


def post(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def get(url):
    return json.loads(urllib.request.urlopen(url).read())


def graph(img, ckpt, denoise, seed, prefix, steps, cfg, pos, neg):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "LoadImage", "inputs": {"image": img}},
        "3": {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["2", 0], "vae": ["1", 2], "tile_size": 512,
                                                          "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                                                   "latent_image": ["3", 0], "seed": seed, "steps": steps, "cfg": cfg,
                                                   "sampler_name": "dpmpp_2m", "scheduler": "karras",
                                                   "denoise": denoise}},
        "7": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["6", 0], "vae": ["1", 2], "tile_size": 512,
                                                         "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8199")
    ap.add_argument("--input-dir", default=r"C:\Users\james\i76-upscale-work\comfy\input")
    ap.add_argument("--image", required=True)
    ap.add_argument("--denoise", type=float, nargs="+", default=[0.2, 0.3])
    ap.add_argument("--ckpt", default="sd_xl_base_1.0.safetensors")
    ap.add_argument("--seed", type=int, default=76)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--pos", default=POS)
    ap.add_argument("--neg", default=NEG)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    name = os.path.basename(a.image)
    shutil.copy(a.image, os.path.join(a.input_dir, name))
    cid = str(uuid.uuid4())
    for d in a.denoise:
        prefix = "h9_%s%s_d%02d" % (os.path.splitext(name)[0], a.tag, round(d * 100))
        t0 = time.time()
        pid = post(a.server + "/prompt", {"prompt": graph(name, a.ckpt, d, a.seed, prefix, a.steps, a.cfg, a.pos, a.neg),
                                          "client_id": cid})["prompt_id"]
        while True:
            h = get(a.server + "/history/" + pid)
            if pid in h and h[pid].get("status", {}).get("completed") is not None:
                break
            if pid in h and h[pid].get("status", {}).get("status_str") == "error":
                break
            time.sleep(2)
        st = h[pid].get("status", {})
        outs = [i["filename"] for o in h[pid].get("outputs", {}).values() for i in o.get("images", [])]
        print(json.dumps({"image": name, "denoise": d, "seconds": round(time.time() - t0, 1),
                          "status": st.get("status_str"), "outputs": outs}), flush=True)
        if st.get("status_str") == "error":
            print(json.dumps(st.get("messages", [])[-1:], indent=1)[:2000])


if __name__ == "__main__":
    main()
