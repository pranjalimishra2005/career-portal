import os
import sys
import asyncio
from app.tools.browser_manager import ensure_default_desktop

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_loop_factory = lambda use_subprocess=False: asyncio.ProactorEventLoop
    except Exception:
        pass

if __name__ == "__main__":
    ensure_default_desktop()
    host = os.environ.get("HOST", "127.0.0.1" if sys.platform == "win32" else "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting AI Job Application Agent API at http://{host}:{port} ...")
    import uvicorn
    loop_target = "asyncio.windows_events:ProactorEventLoop" if sys.platform == "win32" else "auto"
    uvicorn.run(
        "app.backend.main:app",
        host=host,
        port=port,
        reload=False if os.environ.get("PORT") else True,
        loop=loop_target
    )
