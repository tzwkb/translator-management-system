import time

from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from starlette.responses import JSONResponse

PUBLIC_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


def is_public(path):
    return path == "/intake" or path.startswith("/intake-assets/") or path.startswith("/api/public/")


class IntakeHTTP:
    def __init__(self, app):
        self.app = app
        self.clients = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not is_public(scope["path"]):
            return await self.app(scope, receive, send)

        async def send_headers(message):
            if message["type"] == "http.response.start":
                headers = [(key, value) for key, value in message.get("headers", []) if key.decode().lower() not in PUBLIC_HEADERS]
                message = {**message, "headers": headers + [(key.encode(), value.encode()) for key, value in PUBLIC_HEADERS.items()]}
            await send(message)

        async def fail(status, detail, headers=None):
            await JSONResponse({"detail": detail}, status_code=status, headers=headers)(scope, receive, send_headers)

        if scope["path"].startswith("/api/public/"):
            current = time.monotonic()
            self.clients = {key: value for key, value in self.clients.items() if current - value[0] < 60}
            host = (scope.get("client") or ("unknown",))[0]
            started, count = self.clients.get(host, (current, 0))
            if count >= 120 or (host not in self.clients and len(self.clients) >= 4096):
                return await fail(429, "请求过于频繁，请稍后重试 / Too many requests; try again shortly", {"Retry-After": "60"})
            self.clients[host] = (started, count + 1)
        if scope["method"] == "POST":
            headers = dict(scope.get("headers", []))
            if headers.get(b"content-type", b"").split(b";", 1)[0].strip() != b"application/json":
                return await fail(415, "请使用填写页面提交 / Submit through the form")
            body = bytearray()
            while True:
                part = await receive()
                if part["type"] == "http.disconnect":
                    return
                body.extend(part.get("body", b""))
                if len(body) > 128 * 1024:
                    return await fail(413, "资料过长，请缩短说明 / Submission too large; shorten the notes")
                if not part.get("more_body", False):
                    break
            sent = False

            async def replay():
                nonlocal sent
                if sent:
                    return await receive()
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            return await self.app(scope, replay, send_headers)
        return await self.app(scope, receive, send_headers)


def configure_public_http(app):
    app.add_middleware(IntakeHTTP)

    @app.exception_handler(RequestValidationError)
    async def safe_validation_error(request, exc):
        if is_public(request.url.path):
            return JSONResponse({"detail": [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()]}, status_code=422)
        return await request_validation_exception_handler(request, exc)
