"""Loopback-only test server for real transport loss and abrupt process death."""

import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mammoth_os.document_review import DocumentReviews
from mammoth_os.documents import DocumentError, DocumentLibrary
from mammoth_os.llm_completion import Completion


def main():
    root, ready, blocked_index = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    reviews = DocumentReviews(DocumentLibrary(root / "documents", {}))

    class Model:
        model = "offline-recovery-fixture"

        async def generate_completion(self, prompt, **kwargs):
            source = json.loads(prompt.split("\n", 1)[1])
            index = source["chunk_index"]
            with (root / "calls.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"chunk_index": index}) + "\n")
            if index == blocked_index:
                (root / "inflight").write_text(str(index), encoding="utf-8")
                await asyncio.sleep(120)
            return Completion(json.dumps({"summary": "A bounded assessment.", "quote": source["text"][:80]}),
                              finish_reason="stop", usage={"total_tokens": 100}, model=self.model)

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            parts = self.path.split("/")
            try:
                review_id = parts[4]
                if self.command == "GET" and len(parts) == 5:
                    state = reviews.get(review_id)
                elif self.command == "POST" and len(parts) == 6:
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    if parts[5] == "advance" and body.get("confirm_model_usage") is True:
                        state = asyncio.run(reviews.advance(review_id, Model))
                    elif parts[5] == "budget" and body.get("confirm_budget_extension") is True:
                        state = reviews.extend_budget(review_id, body["expected_max_tokens"], body["max_tokens"])
                    else:
                        raise DocumentError("Unsupported test operation.", 400)
                else:
                    raise DocumentError("Unsupported test route.", 404)
                status, payload = 200, {"status": "ok", "review": state}
            except DocumentError as exc:
                status, payload = exc.status_code, {"status": "error", "error": str(exc)}
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = handle_request

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        temporary = ready.with_suffix(".tmp")
        temporary.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}"}), encoding="utf-8")
        temporary.replace(ready)
        server.serve_forever()


if __name__ == "__main__":
    main()
