# Serve o build do Angular e repassa /api para a API do laboratório (porta 8100)
import http.server, http.client, os, socketserver
RAIZ = "/home/administrador/projeto/frontend/dist/sgi-spi/browser"
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=RAIZ, **k)
    def log_message(self, *a): pass
    def _proxy(self):
        n = int(self.headers.get("Content-Length") or 0); corpo = self.rfile.read(n) if n else None
        c = http.client.HTTPConnection("127.0.0.1", 8100, timeout=120)
        cab = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")}
        c.request(self.command, self.path, body=corpo, headers=cab); r = c.getresponse(); dados = r.read()
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"): self.send_header(k, v)
        self.send_header("Content-Length", str(len(dados))); self.end_headers(); self.wfile.write(dados)
    do_POST = do_PUT = do_DELETE = do_PATCH = _proxy
    def do_GET(self):
        if self.path.startswith("/api"): return self._proxy()
        caminho = self.translate_path(self.path.split("?")[0])
        if not os.path.exists(caminho) or os.path.isdir(caminho): self.path = "/index.html"
        return super().do_GET()
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
S(("127.0.0.1", 8200), H).serve_forever()
