#!/usr/bin/env python3
"""Shared whisper worker server.

Keeps a single faster-whisper model in memory and serves multiple subtitle
processes via a Unix domain socket.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

from faster_whisper import WhisperModel


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Shared Whisper socket server")
    p.add_argument("--socket", default="/tmp/amir_whisper_large-v3.sock", help="Unix socket path")
    p.add_argument("--model", default="large-v3", help="Whisper model size/name")
    p.add_argument("--device", default=os.environ.get("AMIR_WHISPER_SERVER_DEVICE", "cpu"), help="cpu/cuda")
    p.add_argument("--compute-type", default=os.environ.get("AMIR_WHISPER_SERVER_COMPUTE", "int8"), help="faster-whisper compute_type")
    return p


async def _serve(args: argparse.Namespace) -> None:
    print(f"Loading model '{args.model}' (device={args.device}, compute_type={args.compute_type})...", flush=True)

    # Memory guard: warn if available RAM is very low
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        # Use psutil if available for RAM; otherwise skip
        try:
            import psutil
            mem = psutil.virtual_memory()
            free_gb = mem.available / (1024 ** 3)
            if free_gb < 3.0:
                print(f"⚠️ WARNING: Only {free_gb:.1f} GB RAM available. Model may crash.", flush=True)
        except ImportError:
            pass
    except Exception:
        pass

    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    print(f"Model loaded successfully.", flush=True)
    lock = asyncio.Lock()
    socket_path = Path(args.socket)

    try:
        if socket_path.exists():
            socket_path.unlink()
    except Exception:
        pass

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await reader.read(1024 * 1024)
            if not data:
                writer.close()
                await writer.wait_closed()
                return

            req: Dict[str, Any] = json.loads(data.decode("utf-8"))

            # Sequential processing: model inference is guarded by a lock.
            async with lock:
                kwargs: Dict[str, Any] = {
                    "word_timestamps": bool(req.get("word_timestamps", True)),
                    "vad_filter": bool(req.get("vad_filter", True)),
                    "temperature": float(req.get("temperature", 0.0)),
                }

                language = req.get("language")
                if language:
                    kwargs["language"] = language

                initial_prompt = req.get("initial_prompt")
                if initial_prompt:
                    kwargs["initial_prompt"] = initial_prompt

                vad_params = req.get("vad_parameters")
                if isinstance(vad_params, dict):
                    kwargs["vad_parameters"] = vad_params

                segments, info = model.transcribe(req["path"], **kwargs)

                # Send info first 
                info_payload = {
                    "type": "info",
                    "language": str(getattr(info, "language", "") or "")
                }
                writer.write((json.dumps(info_payload, ensure_ascii=False) + "\n").encode("utf-8"))
                await writer.drain()

                for seg in segments:
                    seg_words = []
                    if getattr(seg, "words", None):
                        for w in seg.words:
                            seg_words.append({
                                "start": float(w.start),
                                "end": float(w.end),
                                "word": str(w.word),
                            })
                    
                    segment_payload = {
                        "type": "segment",
                        "start": float(getattr(seg, "start", 0.0)),
                        "end": float(getattr(seg, "end", 0.0)),
                        "text": str(getattr(seg, "text", "")),
                        "words": seg_words
                    }
                    writer.write((json.dumps(segment_payload, ensure_ascii=False) + "\n").encode("utf-8"))
                    await writer.drain()

        except Exception as e:
            err = {"error": str(e)}
            try:
                writer.write(json.dumps(err, ensure_ascii=False).encode("utf-8"))
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_unix_server(handle, path=str(socket_path))
    print(f"Whisper server ready on {socket_path}", flush=True)
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_serve(args))


if __name__ == "__main__":
    main()
