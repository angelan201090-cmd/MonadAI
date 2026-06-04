#!/usr/bin/env python3
"""
Monada NPU Proxy — мост между монадой (порты 8081/8082/8083) и lemond (13305).
Каждый порт привязан к своей FLM NPU-модели (recipe: flm, контейнер lemonade-npu).
Форвардит OpenAI-compatible запросы, подставляя нужный model.
"""

import asyncio
import json
import aiohttp
from aiohttp import web

LEMOND_URL = "http://127.0.0.1:13305"

PORT_MODEL_MAP = {
    8081: "gemma3-4b-FLM",     # Head — Lower Manas / Navigator (FLM NPU, ~3-4 GB)
    8082: "lfm2-2.6b-FLM",    # Heart — Kama / Critic          (FLM NPU, 1.8 GB)
    8083: "llama3.1-8b-FLM",   # Body — Higher Manas / Builder  (FLM NPU, 5.5 GB)
}

PORT_DEFAULTS = {
    8081: {"repetition_penalty": 1.05, "frequency_penalty": 0.1},
    8082: {"repetition_penalty": 1.05, "frequency_penalty": 0.1},
    8083: {"repetition_penalty": 1.05, "frequency_penalty": 0.1},
}


async def proxy_handler(request: web.Request) -> web.Response:
    port = request.transport.get_extra_info("sockname")[1]
    model_name = PORT_MODEL_MAP.get(port, "gemma3-4b-FLM")

    try:
        body = await request.json()
    except Exception:
        body = {}

    body["model"] = model_name

    # Инжектируем anti-collapse параметры если не заданы явно
    for param, value in PORT_DEFAULTS.get(port, {}).items():
        if param not in body:
            body[param] = value

    target_path = request.path
    if request.query_string:
        target_path += "?" + request.query_string

    target_url = LEMOND_URL + target_path

    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    headers["Content-Type"] = "application/json"

    is_stream = body.get("stream", False)

    async with aiohttp.ClientSession() as session:
        async with session.post(target_url, json=body, headers=headers) as resp:
            if is_stream:
                response = web.StreamResponse(status=resp.status)
                response.content_type = "text/event-stream"
                await response.prepare(request)
                async for chunk in resp.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
                return response
            else:
                data = await resp.read()
                return web.Response(
                    status=resp.status,
                    body=data,
                    content_type=resp.content_type or "application/json",
                )


async def create_app_for_port(port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_route("*", "/{path_info:.*}", proxy_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    print(f"[NPU-PROXY] Порт {port} → {PORT_MODEL_MAP[port]} @ lemond:13305")
    return runner


async def main():
    runners = []
    for port in PORT_MODEL_MAP:
        runner = await create_app_for_port(port)
        runners.append(runner)
    print("[NPU-PROXY] Все прокси запущены. Ожидаю запросов...")
    try:
        await asyncio.Event().wait()
    finally:
        for r in runners:
            await r.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
